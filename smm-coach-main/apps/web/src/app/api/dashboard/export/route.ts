/**
 * Bundles the tenant's current dashboard state into a single downloadable
 * report so the user can hand it off to a teammate or archive it before
 * regenerating their roadmap. JSON is the source of truth; CSV is a
 * spreadsheet-friendly flattening of the most-asked metrics.
 *
 * Designed to be lightweight (no PDF generation in F) — production PDF
 * lands in Bosqich I.
 */
import { auth } from '@/lib/auth/auth';
import { getDashboardData } from '@/lib/dashboard/data';

type Format = 'json' | 'csv';

// GET so a plain <a href download> works (the archive "Eksport" button is an anchor — it was hitting
// this POST-only route and 405'ing, so the download silently failed). POST kept for programmatic use.
export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) return new Response('unauthorized', { status: 401 });
  const format: Format =
    new URL(req.url).searchParams.get('format') === 'csv' ? 'csv' : 'json';
  return _buildExport(session.user, format);
}

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) return new Response('unauthorized', { status: 401 });
  const body = await req.json().catch(() => ({}));
  const format: Format = body?.format === 'csv' ? 'csv' : 'json';
  return _buildExport(session.user, format);
}

async function _buildExport(
  user: { tenantId: string; name?: string | null; locale?: string | null },
  format: Format,
): Promise<Response> {
  const data = await getDashboardData(user.tenantId, { name: user.name, locale: user.locale });
  if (!data) {
    return new Response('no_dashboard_data', { status: 404 });
  }

  const filename = `smm-dashboard-${data.ig.handle}-${new Date()
    .toISOString()
    .slice(0, 10)}.${format}`;

  if (format === 'csv') {
    return new Response(_toCsv(data), {
      headers: {
        'content-type': 'text/csv; charset=utf-8',
        'content-disposition': `attachment; filename="${filename}"`,
      },
    });
  }

  return new Response(JSON.stringify(data, null, 2), {
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'content-disposition': `attachment; filename="${filename}"`,
    },
  });
}

function _toCsv(d: Awaited<ReturnType<typeof getDashboardData>>): string {
  if (!d) return '';
  const lines: string[] = [];
  const push = (section: string, key: string, value: unknown) =>
    lines.push([section, key, _escape(value)].join(','));

  push('header', 'tenant_handle', d.ig.handle);
  push('header', 'generated_at', new Date().toISOString());
  push('header', 'follower_count', d.ig.followerCount);
  push('header', 'target_followers', d.goal.target);
  push('header', 'weekly_rate', d.goal.weeklyRate.toFixed(1));
  push('header', 'weeks_to_goal', d.goal.weeksToGoal.toFixed(1));

  push('kpi', 'reach_30d', d.kpis.reach30.value);
  push('kpi', 'engagement_rate', d.kpis.engagement.value);

  for (const p of d.pillars) {
    push('pillar', p.name, `${p.sharePct}% · perf=${p.perfScore}`);
  }
  for (const c of d.competitors) {
    push('competitor', c.handle, `${c.followers} · ${c.growthRate.toFixed(1)}%/wk`);
  }
  for (const tp of d.topPosts) {
    push('top_post', tp.permalink || tp.id, `${tp.reach} reach`);
  }

  // CSV header at the very top so spreadsheets render columns properly.
  return ['section,key,value', ...lines].join('\n');
}

function _escape(v: unknown): string {
  const s = v === null || v === undefined ? '' : String(v);
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

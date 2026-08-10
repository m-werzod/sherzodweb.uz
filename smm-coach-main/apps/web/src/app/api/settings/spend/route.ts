/**
 * GET /api/settings/spend
 *
 * Returns this tenant's current LLM spend (today + month-to-date) plus
 * the configured caps so the Settings page can render a "X% of $20 used
 * this month" bar — same data the agents-side budget guard reads.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const tenantId = session.user.tenantId;
  const db = prismaForTenant(tenantId);

  // Aggregate cost from BOTH token_usage (LLMs) and task_media (ElevenLabs,
  // HeyGen, Imagen, Runway). Single source of truth for the cap UI.
  const [monthlyLLM, dailyLLM, monthlyMedia, dailyMedia, perAgentToday, perMediaToday] =
    await Promise.all([
      db.$queryRaw<Array<{ total: number }>>`
        SELECT COALESCE(SUM("costUsd"), 0)::float AS total
        FROM token_usage
        WHERE "tenantId" = ${tenantId}
          AND "createdAt" >= DATE_TRUNC('month', NOW())
      `,
      db.$queryRaw<Array<{ total: number }>>`
        SELECT COALESCE(SUM("costUsd"), 0)::float AS total
        FROM token_usage
        WHERE "tenantId" = ${tenantId}
          AND "createdAt" >= NOW() - INTERVAL '24 hours'
      `,
      db.$queryRaw<Array<{ total: number }>>`
        SELECT COALESCE(SUM("costUsd"), 0)::float AS total
        FROM task_media
        WHERE "tenantId" = ${tenantId}
          AND "createdAt" >= DATE_TRUNC('month', NOW())
      `,
      db.$queryRaw<Array<{ total: number }>>`
        SELECT COALESCE(SUM("costUsd"), 0)::float AS total
        FROM task_media
        WHERE "tenantId" = ${tenantId}
          AND "createdAt" >= NOW() - INTERVAL '24 hours'
      `,
      db.$queryRaw<Array<{ agent: string; cost: number; calls: number }>>`
        SELECT agent, COALESCE(SUM("costUsd"), 0)::float AS cost, COUNT(*)::int AS calls
        FROM token_usage
        WHERE "tenantId" = ${tenantId}
          AND "createdAt" >= NOW() - INTERVAL '24 hours'
        GROUP BY agent
        ORDER BY cost DESC
      `,
      db.$queryRaw<Array<{ provider: string; cost: number; calls: number }>>`
        SELECT provider, COALESCE(SUM("costUsd"), 0)::float AS cost, COUNT(*)::int AS calls
        FROM task_media
        WHERE "tenantId" = ${tenantId}
          AND "createdAt" >= NOW() - INTERVAL '24 hours'
        GROUP BY provider
        ORDER BY cost DESC
      `,
    ]);

  const monthlySpend = (monthlyLLM[0]?.total ?? 0) + (monthlyMedia[0]?.total ?? 0);
  const dailySpend = (dailyLLM[0]?.total ?? 0) + (dailyMedia[0]?.total ?? 0);

  // These match agents-side defaults; override via env on the agents process.
  const monthlyCap = Number(process.env.TENANT_MONTHLY_BUDGET_USD ?? '20');
  const dailyCap = Number(process.env.TENANT_DAILY_BUDGET_USD ?? '3');
  // Tracking-only mode mirrors the agents-side BUDGET_ENFORCE: when off, spend is still counted but
  // the caps never degrade models, so the panel shows "kuzatuv rejimi" instead of a misleading bar.
  const enforce = !['false', '0', 'no', 'off'].includes(
    String(process.env.BUDGET_ENFORCE ?? 'true').toLowerCase(),
  );

  return NextResponse.json({
    enforce,
    monthly: {
      spentUsd: monthlySpend,
      capUsd: monthlyCap,
      percent: monthlyCap > 0 ? Math.min(100, (monthlySpend / monthlyCap) * 100) : 0,
    },
    daily: {
      spentUsd: dailySpend,
      capUsd: dailyCap,
      percent: dailyCap > 0 ? Math.min(100, (dailySpend / dailyCap) * 100) : 0,
    },
    perAgent: perAgentToday.map((r) => ({
      agent: r.agent,
      costUsd: r.cost,
      calls: r.calls,
    })),
    perMediaProvider: perMediaToday.map((r) => ({
      provider: r.provider,
      costUsd: r.cost,
      calls: r.calls,
    })),
    // Explicit allow-list, NOT `x in {…}` — the `in` operator also matches
    // inherited Object.prototype keys (e.g. EMERGENCY_DISABLE_LLM='toString'
    // would falsely report the kill-switch active).
    killSwitch: ['1', 'true', 'yes', 'on'].includes(
      String(process.env.EMERGENCY_DISABLE_LLM ?? '').toLowerCase(),
    ),
  });
}

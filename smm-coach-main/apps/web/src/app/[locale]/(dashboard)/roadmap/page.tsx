import { redirect } from 'next/navigation';
import { Zap, Lock } from 'lucide-react';
import { Link } from '@/i18n/routing';
import { auth } from '@/lib/auth/auth';
import { getRoadmapData, type RoadmapNodeView } from '@/lib/roadmap/data';
import { getDashboardData } from '@/lib/dashboard/data';
import { fmt } from '@/lib/format';
import { GOAL_LABEL_UZ } from '@/lib/goal/kpi';
import { LegendDot } from '@/components/traj/primitives';
import { RoadmapAutoRefresh } from '@/components/traj/roadmap-auto-refresh';
import { ReplanButton } from '@/components/traj/replan-button';

export const dynamic = 'force-dynamic';

const POST_TYPE_LABELS_UZ: Record<string, string> = {
  reel: 'Reel',
  carousel: 'Carousel',
  post: 'Post',
  story: 'Story',
  action: 'Amaliyot',
  station: 'Bekat',
};
function labelForType(t: string | null): string {
  if (!t) return '';
  return POST_TYPE_LABELS_UZ[t] ?? t;
}

export default async function RoadmapPage() {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');

  const [roadmap, dash] = await Promise.all([
    getRoadmapData(session.user.tenantId),
    getDashboardData(session.user.tenantId, { name: session.user.name, locale: session.user.locale }),
  ]);

  if (!roadmap || !dash) {
    // Differentiate "still being generated" from "never started":
    // - dash.onboardingDone === true → AI agents are working, show progress
    // - dash.onboardingDone === false → user hasn't done wizard yet
    const generating = dash?.onboardingDone === true && dash?.roadmapReady === false;
    return (
      <div className="card" style={{ padding: '40px 32px', textAlign: 'center' }}>
        {generating ? (
          <>
            <div
              style={{
                width: 18,
                height: 18,
                borderRadius: '50%',
                background: 'var(--color-accent)',
                margin: '0 auto 18px',
                animation: 'pulse 1.4s ease-in-out infinite',
              }}
            />
            <h1 className="page-title">Yo'l xaritasi shakllanmoqda…</h1>
            <p className="muted" style={{ marginTop: 12, maxWidth: 460, margin: '12px auto 0' }}>
              4 ta AI agent siz uchun trayektoriyani tuzmoqda. Bu odatda 2–5 daqiqa oladi.
              Sahifa tayyor bo'lganda avtomat yangilanadi.
            </p>
            <RoadmapAutoRefresh />
          </>
        ) : (
          <>
            <h1 className="page-title">Yo'l xaritasi yo'q</h1>
            <p className="muted" style={{ marginTop: 10 }}>
              Onboarding'ni tugating yoki yangi roadmap so'rang.
            </p>
            <Link
              href={'/onboarding' as never}
              className="btn primary"
              style={{ marginTop: 20, display: 'inline-block' }}
            >
              Onboarding'ga o'tish
            </Link>
          </>
        )}
      </div>
    );
  }

  // The current task IS the "current stage" — stageMeta was a dead column, so we
  // brief from the in_progress node's real fields instead of "—" placeholders.
  const current = roadmap.nodes.find((n) => n.isCurrent);
  const doneCount = roadmap.nodes.filter((n) => !n.isStation && (n.status === 'complete' || n.status === 'published')).length;

  return (
    <div className="fade-in">
      <div className="topbar">
        <div>
          <div className="eyebrow">YO'L XARITASI · v{roadmap.version}</div>
          <h1 className="page-title">
            {fmt(dash.goal.current)} → <em>{fmt(dash.goal.target)}</em>
          </h1>
          {/* The chosen goal CATEGORY (sales/reach/authority…) drives the whole roadmap's funnel —
              surface it so "what we're optimising for" isn't hidden behind a bare follower count. */}
          {dash.goal.primaryGoal && GOAL_LABEL_UZ[dash.goal.primaryGoal] && (
            <div className="row" style={{ gap: 6, marginTop: 8 }}>
              <span className="tag accent">Maqsad: {GOAL_LABEL_UZ[dash.goal.primaryGoal]}</span>
              {dash.goal.secondaryGoal && GOAL_LABEL_UZ[dash.goal.secondaryGoal] && (
                <span className="tag">+ {GOAL_LABEL_UZ[dash.goal.secondaryGoal]}</span>
              )}
            </div>
          )}
          {/* Goal-aware headline: for sales/reach/engagement the follower gap is
              the wrong metric — show the KPI that actually tracks the user's goal. */}
          {dash.goal.progress && (
            <div className="row" style={{ gap: 8, marginTop: 8, alignItems: 'baseline' }}>
              <span style={{ fontSize: 13, color: 'var(--color-ink-2, #94a3b8)' }}>
                {dash.goal.progress.label}:
              </span>
              <span className="serif" style={{ fontSize: 20 }}>
                {fmt(dash.goal.progress.value)}
                {dash.goal.progress.unit === '%' ? '%' : ` ${dash.goal.progress.unit}`}
              </span>
              {dash.goal.progress.delta != null && dash.goal.progress.delta !== 0 && (
                <span
                  className="mono"
                  style={{
                    fontSize: 12,
                    color:
                      dash.goal.progress.delta > 0
                        ? 'var(--color-good, #10b981)'
                        : 'var(--color-bad, #ef4444)',
                  }}
                >
                  {dash.goal.progress.delta > 0 ? '▲' : '▼'} {Math.abs(dash.goal.progress.delta)}%
                </span>
              )}
              <span className="muted" style={{ fontSize: 11 }}>{dash.goal.progress.caption}</span>
            </div>
          )}
          <div className="muted" style={{ fontSize: 14, maxWidth: 620, marginTop: 8 }}>
            {/* Persister's stored summary used to include "N ta vazifa" baked
                from the agent's pre-insert count — that string then disagreed
                with the right-side pill (which counts actual DB rows). Strip
                that segment so the pill is the only place a task count is
                shown, and they can never disagree again. */}
            {stripTaskCount(roadmap.summary) ??
              "Har bir tugun — bitta topshiriq. Ustiga bosing va to'liq video brief'ni oching."}
          </div>
        </div>
        <div className="topbar-right">
          <span className="pill">{roadmap.totalTasks} TA TOPSHIRIQ</span>
          <span className="pill">{roadmap.totalStations} BEKAT</span>
          <ReplanButton />
        </div>
      </div>

      {dash.profileAuditOpen > 0 && (
        <div
          className="card"
          style={{
            padding: '16px 18px',
            marginBottom: 18,
            borderColor: 'var(--color-accent)',
            background: 'color-mix(in oklch, var(--color-accent) 8%, transparent)',
          }}
        >
          <div className="row" style={{ gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex' }}>
              <Zap size={22} aria-hidden style={{ color: 'var(--color-accent)' }} />
            </div>
            <div style={{ flex: 1, minWidth: 240 }}>
              <div style={{ fontWeight: 600, fontSize: 14 }}>
                Bekat 0 — Profilni tayyorlash
              </div>
              <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
                AI sizning IG profilingizda <strong>{dash.profileAuditOpen} ta kamchilik</strong>{' '}
                aniqladi. Kontent generatsiyasidan oldin shularni tuzating — aks holda eng yaxshi
                videolar ham yangi obunachi keltira olmaydi.
              </div>
            </div>
            <Link href={'/onboarding/profile-review' as never} className="btn primary">
              Profilni tuzatish →
            </Link>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: '14px 18px', marginBottom: 18 }}>
        <div className="row" style={{ gap: 22, flexWrap: 'wrap' }}>
          <LegendDot color="var(--color-good)" label="Bajarilgan" />
          <LegendDot color="var(--color-accent)" label="Joriy" pulse />
          <LegendDot color="var(--color-ink-4)" label="Kelajakda" />
          <span style={{ width: 1, height: 16, background: 'var(--color-line)' }} />
          <span className="mono dim" style={{ fontSize: 11 }}>
            {doneCount}/{roadmap.totalTasks} tugun bajarilgan · {roadmap.totalStations} bekat
          </span>
          <span style={{ marginLeft: 'auto' }} className="row">
            {roadmap.currentTaskId && (
              <Link href={`/task/${roadmap.currentTaskId}` as never} className="btn primary">
                Joriy topshiriqni ochish
              </Link>
            )}
          </span>
        </div>
      </div>

      <div className="roadmap-stage card" style={{ padding: 0 }}>
        <div className="roadmap-track" />
        <div style={{ position: 'relative', padding: '32px 24px 60px' }}>
          {roadmap.nodes.map((n, i) => {
            if (n.isStation) {
              return <StationCard key={n.id} label={n.stationLabel ?? 'Bekat'} title={n.title} />;
            }
            const side: 'left' | 'right' = i % 2 === 0 ? 'left' : 'right';
            return <RoadmapNodeView key={n.id} node={n} side={side} />;
          })}
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: 18,
          marginTop: 18,
        }}
      >
        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">Hozirgi bosqich brifi</div>
              <div className="card-sub">{current?.title ?? 'Boshlash uchun tayyor'}</div>
            </div>
            <span className="tag accent">JORIY</span>
          </div>
          <div className="col">
            <Kpi k="Maqsad" v={`${fmt(current?.followerTarget ?? 0)} obunachi`} />
            <Kpi k="Topshiriqlar" v={`${current?.taskCount ?? 0} ta · ${doneCount} bajarildi`} />
            <Kpi k="Bosh strategiya" v={current?.focus ?? '—'} />
            <Kpi
              k="Risk"
              v={`${roadmap.riskScore != null ? (roadmap.riskScore * 100).toFixed(0) : '—'}%`}
              valueColor={roadmap.riskScore && roadmap.riskScore > 0.3 ? 'var(--color-bad)' : undefined}
            />
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">AI prognoz · trayektoriya</div>
              <div className="card-sub">MONTE CARLO · {dash.forecast?.horizonDays ?? 90} KUN</div>
            </div>
          </div>
          {dash.forecast ? (
            <div className="col">
              <Kpi k="P50" v={fmt(dash.forecast.p50[dash.forecast.p50.length - 1] ?? 0)} />
              <Kpi k="P10 (yomon)" v={fmt(dash.forecast.p10[dash.forecast.p10.length - 1] ?? 0)} />
              <Kpi k="P90 (yaxshi)" v={fmt(dash.forecast.p90[dash.forecast.p90.length - 1] ?? 0)} />
              <Kpi k="Aniqlik" v={`${dash.forecast.accuracyPct?.toFixed(0) ?? '—'}%`} />
              <Kpi k="Joriy sur'at" v={`${fmt(dash.goal.weeklyRate)} / hafta`} />
            </div>
          ) : (
            <p className="muted" style={{ fontSize: 13 }}>
              Prognoz hali yo'q. Forecast worker birinchi run'idan keyin paydo bo'ladi.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function Kpi({ k, v, valueColor }: { k: string; v: string; valueColor?: string }) {
  return (
    <div className="kpi">
      <span className="k">{k}</span>
      <span className="v" style={valueColor ? { color: valueColor } : undefined}>
        {v}
      </span>
    </div>
  );
}

function StationCard({ label, title }: { label: string; title: string }) {
  return (
    <div className="station-card">
      <div className="station-label">{label}</div>
      <div className="station-title">{title}</div>
      <div className="mono dim" style={{ fontSize: 11, marginTop: 8 }}>
        BU YERDA QO'SHIMCHA MASTER-VIDEO MAVZULAR OCHILADI
      </div>
    </div>
  );
}

function RoadmapNodeView({ node, side }: { node: RoadmapNodeView; side: 'left' | 'right' }) {
  const statusClass =
    node.status === 'complete' || node.status === 'published'
      ? 'done'
      : node.isCurrent
        ? 'current'
        : '';
  const cls = `node ${side} ${statusClass}`;
  // Locked = topic-only (no Q&A yet, no script). Action tasks are exempt —
  // the gate only applies to content topics. We show this on the roadmap card
  // so users see at a glance which topics still need their interview.
  const isLocked = !node.scriptUnlocked && !node.hasScript && node.postType !== 'action';
  const inner = (
    <div className="node-card">
      <div className="node-title">{node.title}</div>
      <div className="node-meta">
        {node.followerTarget && <span>→ {fmt(node.followerTarget)}</span>}
        {node.postType && <span>· {labelForType(node.postType)}</span>}
        {node.isCurrent && <span style={{ color: 'var(--color-accent)' }}>· OCHISH</span>}
      </div>
      {node.focus && (
        <div style={{ fontSize: 12, color: 'var(--color-ink-2)', marginTop: 8 }}>{node.focus}</div>
      )}
      {isLocked && (
        <div
          style={{
            marginTop: 10,
            fontSize: 11,
            color: 'var(--color-accent)',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            padding: '2px 8px',
            borderRadius: 999,
            border: '1px solid color-mix(in oklch, var(--color-accent) 35%, transparent)',
            background: 'color-mix(in oklch, var(--color-accent) 8%, transparent)',
          }}
          title="Bu mavzu uchun avval AI bilan suhbat o'tkazish kerak"
        >
          <Lock size={11} aria-hidden /> Suhbat kerak
        </div>
      )}
      {(node.status === 'complete' || node.status === 'published') && (
        <div className="bar" style={{ height: 4, marginTop: 14 }}>
          <span style={{ width: '100%' }} />
        </div>
      )}
      {node.isCurrent && (
        <div className="bar" style={{ height: 4, marginTop: 14 }}>
          <span style={{ width: '40%' }} />
        </div>
      )}
    </div>
  );
  // Every content task is clickable — opens the full brief. Only stations
  // (which render via StationCard above) are non-interactive.
  return (
    <div className={cls}>
      <div className="node-marker">
        <div className="inner" />
      </div>
      <Link
        href={`/task/${node.id}` as never}
        style={{
          gridColumn: side === 'left' ? 1 : 3,
          textDecoration: 'none',
          color: 'inherit',
          cursor: 'pointer',
        }}
      >
        {inner}
      </Link>
    </div>
  );
}

/**
 * Strip "{N} ta vazifa, " (and variants) from the persister's stored
 * summary. The pill on the right already shows the authoritative DB
 * count; surfacing the persister's pre-insert count alongside it just
 * confuses users when the two numbers don't match (e.g. one task
 * silently failed to insert).
 */
function stripTaskCount(s: string | null | undefined): string | null {
  if (!s) return null;
  return s
    .replace(/\s*[—\-,·]?\s*\d+\s*ta\s+vazifa\s*,?\s*/i, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

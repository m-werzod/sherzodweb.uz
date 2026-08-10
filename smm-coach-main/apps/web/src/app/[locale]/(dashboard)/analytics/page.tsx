/**
 * /analytics — follower trajectory chart.
 *
 * Reads:
 *   - follower_snapshots (history, oxirgi 60 kun)
 *   - forecasts (oxirgi P10/P50/P90, horizonDays kelajak)
 *   - prediction_audits (resolved accuracy oxirgi 30 kun)
 *
 * Pure SVG chart — inline (multi-line + area + axes); no chart lib.
 */
import { redirect } from 'next/navigation';
import { getTranslations } from 'next-intl/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { RATE_LABEL_UZ } from '@/lib/goal/kpi';

// Uzbek label per audited metric for the per-KPI accuracy breakdown. Rate
// metrics come from the shared map; 'reach' is the raw count audited at publish.
const METRIC_LABEL_UZ: Record<string, string> = { ...RATE_LABEL_UZ, reach: 'Qamrov (reach)' };

export const dynamic = 'force-dynamic';

type SnapshotPoint = { day: number; followers: number; takenAt: Date };
type ForecastPoint = { day: number; p10: number; p50: number; p90: number };

async function loadData(tenantId: string) {
  const db = prismaForTenant(tenantId);

  const since = new Date(Date.now() - 60 * 86_400_000);
  const [snapshots, forecast, audits, kpiRows, sourceRows] = await Promise.all([
    db.followerSnapshot.findMany({
      where: { takenAt: { gte: since } },
      orderBy: { takenAt: 'asc' },
      select: { count: true, takenAt: true },
    }),
    db.forecast.findFirst({
      orderBy: { runAt: 'desc' },
      select: { p10: true, p50: true, p90: true, horizonDays: true, runAt: true, accuracyPct: true },
    }),
    db.$queryRaw<Array<{ n: bigint; correct: bigint }>>`
      SELECT COUNT(*) AS n,
             SUM(CASE WHEN ABS(error) <= 0.10 THEN 1 ELSE 0 END) AS correct
      FROM prediction_audits
      WHERE "tenantId" = ${tenantId}
        AND "resolvedAt" IS NOT NULL
        AND "resolvedAt" > NOW() - INTERVAL '30 days'
    `,
    // Per-KPI accuracy: same window, grouped by metric. mean_err → accuracy via
    // the shared (1 - AVG(|error|)) * 100 clamp, so it agrees with the forecast pill.
    db.$queryRaw<Array<{ metric: string; n: bigint; acc: number | null }>>`
      SELECT metric, COUNT(*) AS n,
             AVG(CASE WHEN (1 + error) > 0
                      THEN LEAST(1 + error, 1.0 / (1 + error))
                      ELSE 0 END)::float8 AS acc
      FROM prediction_audits
      WHERE "tenantId" = ${tenantId}
        AND "resolvedAt" IS NOT NULL
        AND error IS NOT NULL
        AND "resolvedAt" > NOW() - INTERVAL '30 days'
      GROUP BY metric
      ORDER BY metric
    `,
    // Per-SOURCE accuracy: which signal backing a reach prediction was most accurate
    // (exemplar / forecast / baseline). source is NULL on pre-provenance rows, so this
    // fills in only as new predictions resolve. Backtest by provenance, not just mean.
    db.$queryRaw<Array<{ source: string; n: bigint; acc: number | null }>>`
      SELECT source, COUNT(*) AS n,
             AVG(CASE WHEN (1 + error) > 0
                      THEN LEAST(1 + error, 1.0 / (1 + error))
                      ELSE 0 END)::float8 AS acc
      FROM prediction_audits
      WHERE "tenantId" = ${tenantId}
        AND source IS NOT NULL
        AND "resolvedAt" IS NOT NULL
        AND error IS NOT NULL
        AND "resolvedAt" > NOW() - INTERVAL '30 days'
      GROUP BY source
      ORDER BY source
    `,
  ]);

  // Day 0 = bugun. Snapshotlar manfiy kun (oxirgi kunlar), forecast kelajak kunlar.
  const now = Date.now();
  const snapshotPoints: SnapshotPoint[] = snapshots.map((s) => ({
    day: Math.round((s.takenAt.getTime() - now) / 86_400_000),
    followers: s.count,
    takenAt: s.takenAt,
  }));

  const forecastPoints: ForecastPoint[] = forecast
    ? (forecast.p50 as number[]).map((p50, i) => ({
        day: i + 1,
        p10: (forecast.p10 as number[])[i] ?? p50,
        p50,
        p90: (forecast.p90 as number[])[i] ?? p50,
      }))
    : [];

  const auditRow = audits[0];
  const auditN = auditRow ? Number(auditRow.n) : 0;
  const auditCorrect = auditRow ? Number(auditRow.correct) : 0;
  const accuracy30d = auditN > 0 ? Math.round((auditCorrect / auditN) * 100) : null;

  // `acc` is a per-row SYMMETRIC accuracy averaged in SQL — min(ratio, 1/ratio)
  // where ratio = actual/predicted — so a post that BEAT its (count) reach
  // prediction scores high instead of collapsing to 0% under the old
  // (1-|error|) clamp (reach over-performance is unbounded on the upside).
  const kpiAccuracy = kpiRows.map((r) => ({
    metric: r.metric,
    label: METRIC_LABEL_UZ[r.metric] ?? r.metric,
    n: Number(r.n),
    accuracyPct: Math.max(0, Math.min(100, Math.round((r.acc ?? 0) * 100))),
  }));

  const SOURCE_LABEL_UZ: Record<string, string> = {
    exemplar: 'Namuna-post asosida',
    forecast: 'Prognoz modeli',
    baseline: "O'z o'rtachasi",
  };
  const sourceAccuracy = sourceRows.map((r) => ({
    source: r.source,
    label: SOURCE_LABEL_UZ[r.source] ?? r.source,
    n: Number(r.n),
    accuracyPct: Math.max(0, Math.min(100, Math.round((r.acc ?? 0) * 100))),
  }));

  return { snapshotPoints, forecastPoints, forecast, accuracy30d, auditN, kpiAccuracy, sourceAccuracy };
}

export default async function AnalyticsPage() {
  const t = await getTranslations();
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');

  const data = await loadData(session.user.tenantId);

  return (
    <div className="fade-in" style={{ padding: '24px 0' }}>
      <div className="topbar" style={{ marginBottom: 20 }}>
        <div>
          <div className="eyebrow">ANALITIKA</div>
          <h1 className="page-title">{t('nav.analytics')}</h1>
          <div className="muted" style={{ fontSize: 13, maxWidth: 620, marginTop: 6 }}>
            Follower o'sish tarixi va prognoz · daily_snapshot worker har kuni
            00:05 da follower count yozadi, forecast worker har kuni 02:00 da
            P10/P50/P90 trajectory tuzadi.
          </div>
        </div>
        <div className="topbar-right">
          {data.accuracy30d != null ? (
            <span className="pill">
              <span className="live-dot" />
              Prognoz aniqligi · {data.accuracy30d}% ({data.auditN} ta resolved)
            </span>
          ) : (
            <span className="pill" style={{ opacity: 0.55 }}>
              Prognoz aniqligi · ma'lumot to'planmoqda
            </span>
          )}
        </div>
      </div>

      {data.snapshotPoints.length < 2 && data.forecastPoints.length === 0 ? (
        // <2 snapshots can't draw a trajectory (a single point renders a bare dot
        // + a misleading "KELAJAK 0 KUN") — show the cold-start state instead.
        <EmptyState />
      ) : (
        <div className="card" style={{ padding: 20 }}>
          <div className="card-head" style={{ marginBottom: 12 }}>
            <div>
              <div className="card-title">Follower trajectoriyasi</div>
              <div className="card-sub">
                OXIRGI {data.snapshotPoints.length} KUN · KELAJAK {data.forecastPoints.length} KUN
              </div>
            </div>
            <div className="row" style={{ gap: 12 }}>
              <Legend swatch="rgba(6, 182, 212, 0.95)" label="Haqiqiy" solid />
              <Legend swatch="rgba(168, 85, 247, 0.95)" label="P50 prognoz" dashed />
              <Legend swatch="rgba(168, 85, 247, 0.20)" label="P10–P90 koridor" area />
            </div>
          </div>
          <TrajectoryChart snapshots={data.snapshotPoints} forecast={data.forecastPoints} />
        </div>
      )}

      {data.kpiAccuracy.length > 0 && (
        <div className="card" style={{ padding: 16, marginTop: 16 }}>
          <div className="card-head">
            <div>
              <div className="card-title">Maqsad KPI aniqligi</div>
              <div className="card-sub">OXIRGI 30 KUN · METRIKA BO'YICHA · (1 − o'rtacha xato)</div>
            </div>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 12 }}>
            {data.kpiAccuracy.map((k) => (
              <span
                key={k.metric}
                className="pill"
                style={{
                  borderColor:
                    k.accuracyPct >= 70
                      ? 'color-mix(in oklch, var(--color-good, #10b981) 50%, var(--color-line))'
                      : 'color-mix(in oklch, var(--color-warm, #f59e0b) 50%, var(--color-line))',
                }}
              >
                {k.label} · {k.accuracyPct}%{' '}
                <span className="dim" style={{ fontSize: 11 }}>
                  ({k.n} ta)
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {data.sourceAccuracy.length > 0 && (
        <div className="card" style={{ padding: 16, marginTop: 16 }}>
          <div className="card-head">
            <div>
              <div className="card-title">Manba bo'yicha aniqlik</div>
              <div className="card-sub">
                OXIRGI 30 KUN · QAYSI SIGNAL ENG ANIQ PROGNOZ BERDI · (1 − o'rtacha xato)
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 12 }}>
            {data.sourceAccuracy.map((s) => (
              <span
                key={s.source}
                className="pill"
                style={{
                  borderColor:
                    s.accuracyPct >= 70
                      ? 'color-mix(in oklch, var(--color-good, #10b981) 50%, var(--color-line))'
                      : 'color-mix(in oklch, var(--color-warm, #f59e0b) 50%, var(--color-line))',
                }}
              >
                {s.label} · {s.accuracyPct}%{' '}
                <span className="dim" style={{ fontSize: 11 }}>
                  ({s.n} ta)
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 16, marginTop: 16 }}>
        <div className="card-head">
          <div>
            <div className="card-title">Ma'lumot manbai</div>
            <div className="card-sub">QAYSI WORKER QAYSI MA'LUMOTNI YOZADI</div>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
          <DataSourceCard
            title="daily_snapshot"
            cadence="Har kuni 00:05 (Asia/Tashkent)"
            desc={`${data.snapshotPoints.length} ta nuqta · Instagram follower count + activity heatmap`}
          />
          <DataSourceCard
            title="forecast"
            cadence="Har kuni 02:00"
            desc={
              data.forecast
                ? `P10/P50/P90 trajectory · horizon ${data.forecast.horizonDays} kun · oxirgi run ${data.forecast.runAt.toLocaleDateString('uz-UZ')}`
                : 'Hali ishlamagan — daily_snapshot 7+ kunlik ma\'lumot to\'plagach boshlanadi'
            }
          />
          <DataSourceCard
            title="prediction_resolver"
            cadence="Har 24 soatda"
            desc={
              data.accuracy30d != null
                ? `${data.auditN} ta bashorat resolved · ±10% to'g'rilik = ${data.accuracy30d}%`
                : 'Hali resolved bashorat yo\'q — beta user IG\'ga post qilgach to\'lib boradi'
            }
          />
          <DataSourceCard
            title="account_tracker"
            cadence="Har 6 soatda (tracker_pulse)"
            desc="IG metrikalar (reach, saves, comments) root-cause tahlili · keyingi sprint /agents da live"
          />
        </div>
      </div>
    </div>
  );
}

function Legend({ swatch, label, dashed, solid, area }: { swatch: string; label: string; dashed?: boolean; solid?: boolean; area?: boolean }) {
  return (
    <span className="row" style={{ alignItems: 'center', gap: 6, fontSize: 11 }}>
      {area ? (
        <span style={{ width: 14, height: 8, background: swatch, borderRadius: 2 }} />
      ) : (
        <svg width="18" height="8" viewBox="0 0 18 8">
          <line
            x1="0"
            y1="4"
            x2="18"
            y2="4"
            stroke={swatch}
            strokeWidth="2"
            strokeDasharray={dashed ? '4 3' : undefined}
          />
        </svg>
      )}
      <span style={{ color: 'var(--color-ink-2, #94a3b8)' }}>{label}</span>
    </span>
  );
}

function DataSourceCard({ title, cadence, desc }: { title: string; cadence: string; desc: string }) {
  return (
    <div
      style={{
        padding: 12,
        borderRadius: 8,
        background: 'var(--color-bg-elev)',
        border: '1px solid var(--color-line)',
      }}
    >
      <div className="row" style={{ alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span className="mono" style={{ fontSize: 12, color: 'var(--color-accent)' }}>{title}</span>
        <span className="muted" style={{ fontSize: 10 }}>· {cadence}</span>
      </div>
      <div style={{ fontSize: 12, color: 'var(--color-ink-2)', lineHeight: 1.4 }}>{desc}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="card" style={{ padding: 32, textAlign: 'center' }}>
      <div style={{ fontSize: 14, color: 'var(--color-ink-2)', marginBottom: 8 }}>
        Hozircha snapshot va prognoz yo'q.
      </div>
      <div className="muted" style={{ fontSize: 12, maxWidth: 420, margin: '0 auto' }}>
        daily_snapshot worker har kuni 00:05 da Instagram follower count'ni yozadi.
        7+ kun ma'lumot yig'ilgach forecast worker P10/P50/P90 prognoz tuza boshlaydi.
      </div>
    </div>
  );
}

/**
 * Pure-SVG multi-line chart. X axis: kun (snapshot manfiy, forecast musbat).
 * Y axis: follower count (auto-scaled). Snapshots solid cyan; forecast P50
 * dashed purple; P10-P90 koridor purple area fill.
 */
function TrajectoryChart({
  snapshots,
  forecast,
}: {
  snapshots: SnapshotPoint[];
  forecast: ForecastPoint[];
}) {
  const width = 920;
  const height = 280;
  const padding = { top: 16, right: 24, bottom: 32, left: 56 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  // X domain: oxirgi snapshot kun → so'nggi forecast kun.
  const allDays = [...snapshots.map((s) => s.day), ...forecast.map((f) => f.day)];
  const xMin = allDays.length ? Math.min(...allDays) : -30;
  const xMax = allDays.length ? Math.max(...allDays) : 14;
  const xSpan = Math.max(1, xMax - xMin);

  // Y domain: barcha nuqtalar diapazoni, 5% padding bilan.
  const allY: number[] = [
    ...snapshots.map((s) => s.followers),
    ...forecast.flatMap((f) => [f.p10, f.p50, f.p90]),
  ];
  if (allY.length === 0) return null;
  const yMinRaw = Math.min(...allY);
  const yMaxRaw = Math.max(...allY);
  const yPad = (yMaxRaw - yMinRaw) * 0.05 || 10;
  const yMin = Math.max(0, yMinRaw - yPad);
  const yMax = yMaxRaw + yPad;
  const ySpan = Math.max(1, yMax - yMin);

  const xScale = (day: number) => padding.left + ((day - xMin) / xSpan) * innerW;
  const yScale = (val: number) => padding.top + (1 - (val - yMin) / ySpan) * innerH;

  const snapshotPath = snapshots
    .map((s, i) => `${i === 0 ? 'M' : 'L'}${xScale(s.day).toFixed(1)} ${yScale(s.followers).toFixed(1)}`)
    .join(' ');

  const forecastP50Path = forecast
    .map((f, i) => `${i === 0 ? 'M' : 'L'}${xScale(f.day).toFixed(1)} ${yScale(f.p50).toFixed(1)}`)
    .join(' ');

  // P10/P90 koridor — pastdan tepaga to'liq yopiq path.
  const corridorPath = forecast.length
    ? [
        ...forecast.map(
          (f, i) => `${i === 0 ? 'M' : 'L'}${xScale(f.day).toFixed(1)} ${yScale(f.p90).toFixed(1)}`,
        ),
        ...forecast
          .slice()
          .reverse()
          .map((f) => `L${xScale(f.day).toFixed(1)} ${yScale(f.p10).toFixed(1)}`),
        'Z',
      ].join(' ')
    : '';

  // Y axis ticks — 5 ta.
  const yTicks = Array.from({ length: 5 }, (_, i) => {
    const val = yMin + (ySpan * i) / 4;
    return { val, label: formatFollowers(val), y: yScale(val) };
  });

  // X axis ticks — har 7 kun.
  const xTicks: Array<{ day: number; label: string }> = [];
  for (let d = Math.ceil(xMin / 7) * 7; d <= xMax; d += 7) {
    xTicks.push({ day: d, label: d === 0 ? 'bugun' : d > 0 ? `+${d}k` : `${d}k` });
  }

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
      {/* Y grid lines */}
      {yTicks.map((t, i) => (
        <line
          key={i}
          x1={padding.left}
          x2={width - padding.right}
          y1={t.y}
          y2={t.y}
          stroke="var(--color-line)"
          strokeWidth="1"
          opacity="0.3"
        />
      ))}

      {/* Vertical "bugun" guide */}
      <line
        x1={xScale(0)}
        x2={xScale(0)}
        y1={padding.top}
        y2={height - padding.bottom}
        stroke="var(--color-line)"
        strokeWidth="1"
        strokeDasharray="3 3"
        opacity="0.6"
      />

      {/* Forecast koridor (area) */}
      {corridorPath && (
        <path d={corridorPath} fill="rgba(168, 85, 247, 0.18)" stroke="none" />
      )}

      {/* Snapshot line */}
      {snapshotPath && (
        <path
          d={snapshotPath}
          fill="none"
          stroke="rgba(6, 182, 212, 0.95)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}

      {/* Forecast P50 dashed */}
      {forecastP50Path && (
        <path
          d={forecastP50Path}
          fill="none"
          stroke="rgba(168, 85, 247, 0.95)"
          strokeWidth="2"
          strokeDasharray="5 4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}

      {/* Snapshot dots */}
      {snapshots.map((s, i) => (
        <circle
          key={i}
          cx={xScale(s.day)}
          cy={yScale(s.followers)}
          r="2.5"
          fill="rgba(6, 182, 212, 1)"
        />
      ))}

      {/* Y axis labels */}
      {yTicks.map((t, i) => (
        <text
          key={i}
          x={padding.left - 8}
          y={t.y + 4}
          textAnchor="end"
          fontSize="10"
          fill="var(--color-ink-3, #64748b)"
          className="mono"
        >
          {t.label}
        </text>
      ))}

      {/* X axis labels */}
      {xTicks.map((t, i) => (
        <text
          key={i}
          x={xScale(t.day)}
          y={height - padding.bottom + 16}
          textAnchor="middle"
          fontSize="10"
          fill="var(--color-ink-3, #64748b)"
          className="mono"
        >
          {t.label}
        </text>
      ))}
    </svg>
  );
}

function formatFollowers(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(n >= 10_000 ? 0 : 1)}K`;
  return Math.round(n).toString();
}

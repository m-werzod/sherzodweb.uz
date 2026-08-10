import { redirect } from 'next/navigation';
import { Link } from '@/i18n/routing';
import { auth } from '@/lib/auth/auth';
import { getDashboardData, type DashboardData, type AgentKind } from '@/lib/dashboard/data';
import { AGENTS } from '@/lib/agents/config';
import { fmt } from '@/lib/format';
import { GOAL_LABEL_UZ } from '@/lib/goal/kpi';
import {
  AgentAvatar,
  BarList,
  Delta,
  GrowthChart,
  Sparkline,
  StickFigure,
} from '@/components/traj/primitives';
import { DashboardActions } from '@/components/traj/dashboard-actions';

export const dynamic = 'force-dynamic';

export default async function DashboardPage({
  searchParams,
}: {
  searchParams?: Promise<{ ig_error?: string; ig_detail?: string; ig?: string }>;
}) {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');

  const data = await getDashboardData(session.user.tenantId, {
    name: session.user.name,
    locale: session.user.locale,
  });
  if (!data) redirect('/onboarding');

  const params = (await searchParams) ?? {};
  return (
    <DashboardView
      data={data}
      igError={params.ig_error ?? null}
      igDetail={params.ig_detail ?? null}
    />
  );
}

function DashboardView({
  data,
  igError,
  igDetail,
}: {
  data: DashboardData;
  igError?: string | null;
  igDetail?: string | null;
}) {
  const igErrorLabel = igError ? igErrorMessage(igError) : null;
  const goalPct = (data.goal.current / data.goal.target) * 100;
  const firstName = data.user.name.split(' ')[0] ?? data.user.name;
  const remaining = data.goal.target - data.goal.current;

  return (
    <div className="fade-in">
      <div className="topbar">
        <div>
          {/* BB31: "DASHBOARD · @handle" read as a clickable breadcrumb
              trail. The section is already obvious from the nav, so lead
              with the account identity (the useful context) and drop the
              redundant "DASHBOARD ·" crumb. */}
          <div className="eyebrow">
            BOSH PANEL
            <span style={{ color: 'var(--color-ink-3)', marginLeft: 6 }}>
              @{data.ig.handle}
            </span>
          </div>
          <h1 className="page-title">
            Salom, <em>{firstName}</em>.
          </h1>
          <div className="muted" style={{ fontSize: 14, maxWidth: 600, marginTop: 8 }}>
            {/* BB19: a fresh user with streak.today === 0 used to read
                "Bugun 0-kun streak'da" — which lands as failure on day one.
                Reframe to an invitation. Once they post and the streak
                ticks up, the normal celebratory copy returns. */}
            {data.streak.today > 0 ? (
              <>
                Bugun{' '}
                <span className="serif" style={{ color: 'var(--color-good)', fontSize: 18 }}>
                  {data.streak.today}-kun
                </span>{' '}
                streak&apos;da.{' '}
              </>
            ) : (
              <>
                <span className="serif" style={{ color: 'var(--color-accent)', fontSize: 18 }}>
                  Birinchi kuningiz
                </span>{' '}
                — birinchi vazifani bajarib, streak&apos;ni boshlang.{' '}
              </>
            )}
            Maqsadgacha {fmt(remaining)} obunachi qoldi — joriy sur&apos;atda{' '}
            <span className="mono" style={{ color: 'var(--color-ink)' }}>
              {data.goal.weeksToGoal} hafta
            </span>{' '}
            kerak bo&apos;ladi.
          </div>
        </div>
        <div className="topbar-right" style={{ position: 'relative' }}>
          {/* Pill label reflects REAL agent activity in the last hour, not
              the static AGENTS config (which used to print "4 AGENT JONLI"
              even on a brand-new tenant where nothing had ever run). */}
          <DashboardActions agentCount={data.agentsLiveCount} />
        </div>
      </div>

      {/* Instagram OAuth error banner — set by the callback redirecting back
          to /dashboard?ig_error=... when something went wrong (state mismatch,
          token exchange failed, Meta returned an error). Previously the
          callback always pushed to /sign-in on failure which logged the user
          out. Now we keep the session and surface the reason inline. */}
      {igErrorLabel && (
        <div
          className="card"
          style={{
            padding: '12px 16px',
            marginBottom: 14,
            background: 'color-mix(in oklch, var(--color-bad, #dc2626) 8%, var(--color-surface))',
            borderColor: 'var(--color-bad, #dc2626)',
            fontSize: 13,
            color: 'var(--color-ink)',
          }}
        >
          <strong style={{ color: 'var(--color-bad, #dc2626)' }}>Instagram ulanmadi.</strong>{' '}
          {igErrorLabel} Sessiyangiz saqlanib qoldi — qaytadan urinib ko&apos;ring.
          {igDetail && (
            <div
              className="mono"
              style={{
                marginTop: 8,
                padding: '8px 10px',
                background: 'var(--color-bg-elev)',
                borderRadius: 6,
                fontSize: 11,
                lineHeight: 1.5,
                color: 'var(--color-ink-2)',
                wordBreak: 'break-word',
              }}
            >
              Meta javobi: {igDetail}
            </div>
          )}
        </div>
      )}

      {/* Instagram connect prompt — shows only when no OAuth token saved.
          Clicking the CTA fires the Business Login OAuth flow which pulls
          followers, posts, like/comment counts, reach, and audience
          demographics. */}
      {!data.igConnected && (
        <div
          className="card"
          style={{
            padding: '14px 18px',
            marginBottom: 18,
            background: 'color-mix(in oklch, var(--color-accent) 12%, var(--color-surface))',
            borderColor: 'var(--color-accent)',
          }}
        >
          <div
            className="row"
            style={{ gap: 14, alignItems: 'center', flexWrap: 'wrap' }}
          >
            <div style={{ flex: 1, minWidth: 240 }}>
              <div className="eyebrow" style={{ color: 'var(--color-accent)' }}>
                INSTAGRAM ULANMAGAN
              </div>
              <div style={{ fontSize: 14, color: 'var(--color-ink)', marginTop: 4 }}>
                Real obunachi, post, reach va auditoriya ma&apos;lumotlari uchun Instagram&apos;ni
                Meta Business Login orqali rasmiy ulang. Bir bosish.
              </div>
            </div>
            {/* OAuth dance hops to /api/auth/instagram/start which Meta
                redirects to instagram.com — must be a raw anchor, not a
                Next.js <Link>. */}
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
            <a
              href="/api/auth/instagram/start?return=/dashboard"
              className="btn primary"
              style={{ whiteSpace: 'nowrap' }}
            >
              Instagram&apos;ni ulash →
            </a>
          </div>
        </div>
      )}

      {/* Budget low warning — premium models silently degrade to Haiku once
          we cross the cap. Better to warn the user than let them notice
          script quality drop without explanation. */}
      {data.budget.percent >= 90 && (
        <div
          className="card"
          style={{
            padding: '14px 18px',
            marginBottom: 14,
            background: 'color-mix(in oklch, var(--color-bad, #EF4444) 8%, transparent)',
            borderColor: 'var(--color-bad, #EF4444)',
          }}
        >
          <div className="row" style={{ gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ fontSize: 18 }}>⚠️</div>
            <div style={{ flex: 1, minWidth: 220 }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                AI budget cap: ${data.budget.spentUsd.toFixed(2)} / ${data.budget.capUsd}
                {' '}({data.budget.percent.toFixed(0)}%)
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                Cap'ga yetilganda script'lar Opus o'rniga Haiku'da yoziladi (arzon, sifati biroz past).
                Settings → Sarflar'da limit oshiring.
              </div>
            </div>
            <Link href={'/settings' as never} className="btn">
              Sarflarni ko'rish
            </Link>
          </div>
        </div>
      )}

      {/* "Boshlash" CTA — there's a JORIY task waiting. Highest-priority
          banner; appears before profile audit so users always know what's
          next instead of staring at planned cards. */}
      {data.currentTask && (
        <div
          className="card"
          style={{
            padding: '16px 20px',
            marginBottom: 18,
            background: 'color-mix(in oklch, var(--color-accent) 12%, var(--color-surface))',
            borderColor: 'var(--color-accent)',
          }}
        >
          <div className="row" style={{ gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ fontSize: 22, lineHeight: 1 }}>▶</div>
            <div style={{ flex: 1, minWidth: 240 }}>
              <div className="eyebrow" style={{ color: 'var(--color-accent)' }}>
                JORIY VAZIFA
              </div>
              <div style={{ fontSize: 14, color: 'var(--color-ink)', marginTop: 4 }}>
                {data.currentTask.hasScript ? (
                  <>
                    <strong>{data.currentTask.title}</strong> — to'liq brief, ovoz, thumbnail va kadr
                    pozitsiyalari tayyor. Boshlang.
                  </>
                ) : (
                  <>
                    <strong>{data.currentTask.title}</strong> — birinchi mavzuni oching: AI savol
                    beradi va javoblaringiz asosida senariy yozadi.
                  </>
                )}
              </div>
            </div>
            <Link
              href={`/task/${data.currentTask.id}` as never}
              className="btn primary"
              style={{ whiteSpace: 'nowrap' }}
            >
              {data.currentTask.hasScript ? 'Vazifani boshlash →' : 'Mavzuni ochish →'}
            </Link>
          </div>
        </div>
      )}

      {/* Profile audit reminder — connected but the AI checklist isn't done
          yet. We show this once OAuth is in place but before the user has
          fixed/skipped all items. */}
      {data.igConnected && data.profileAuditPending && (
        <div
          className="card"
          style={{
            padding: '14px 18px',
            marginBottom: 18,
            background: 'color-mix(in oklch, var(--color-warm) 12%, var(--color-surface))',
            borderColor: 'var(--color-warm)',
          }}
        >
          <div className="row" style={{ gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 240 }}>
              <div className="eyebrow" style={{ color: 'var(--color-warm)' }}>
                PROFIL TAHLILI · {data.profileAuditScore ?? 0}/100
              </div>
              <div style={{ fontSize: 14, color: 'var(--color-ink)', marginTop: 4 }}>
                AI sizning Instagram profilingiz uchun {data.profileAuditOpen ?? 0} ta professional
                yaxshilanish topdi (bio, link, highlights). Bir necha daqiqada bajaring.
              </div>
            </div>
            <Link
              href={'/onboarding/profile-review' as never}
              className="btn primary"
              style={{ whiteSpace: 'nowrap' }}
            >
              Tahlilni ochish →
            </Link>
          </div>
        </div>
      )}

      {/* Post audit — Faza 2 post_analyzer: the AI's deep read of the user's
          OWN posts (visual quality + cross-post weaknesses + audience wants).
          Shown once the onboarding_post_audit workflow has produced a
          deepAnalysis. These weaknesses are what the next roadmap targets. */}
      {data.postAudit && (
        <div className="card" style={{ padding: '18px 22px', marginBottom: 18 }}>
          <div className="card-head">
            <div>
              <div className="card-title">Post audit · AI chuqur tahlil</div>
              <div className="card-sub">
                {data.postAudit.analyzedPosts} POST TAHLIL QILINDI
                {data.postAudit.avgQuality != null && (
                  <> · VIZUAL SIFAT {data.postAudit.avgQuality}/100</>
                )}
              </div>
            </div>
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: data.postAudit.weaknesses.length > 0 ? '1.2fr 1fr' : '1fr',
              gap: 22,
            }}
          >
            {data.postAudit.weaknesses.length > 0 && (
              <div>
                <div
                  className="eyebrow"
                  style={{ marginBottom: 10, color: 'var(--color-bad, #ef4444)' }}
                >
                  ANIQLANGAN KAMCHILIKLAR · YO&apos;L XARITASI YECHADI
                </div>
                <ul style={{ margin: 0, paddingLeft: 18, display: 'grid', gap: 8 }}>
                  {data.postAudit.weaknesses.map((w, i) => (
                    <li key={i} style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--color-ink)' }}>
                      {w}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="col" style={{ gap: 16 }}>
              {data.postAudit.visualPatterns.length > 0 && (
                <div>
                  <div className="eyebrow" style={{ marginBottom: 8 }}>VIZUAL PATTERN</div>
                  <ul style={{ margin: 0, paddingLeft: 18, display: 'grid', gap: 6 }}>
                    {data.postAudit.visualPatterns.map((p, i) => (
                      <li key={i} style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--color-ink-2)' }}>
                        {p}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {data.postAudit.audienceInsights.length > 0 && (
                <div>
                  <div className="eyebrow" style={{ marginBottom: 8, color: 'var(--color-warm)' }}>
                    AUDITORIYA NIMA XOHLAYDI
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18, display: 'grid', gap: 6 }}>
                    {data.postAudit.audienceInsights.map((a, i) => (
                      <li key={i} style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--color-ink-2)' }}>
                        {a}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Goal banner — verbatim port of front/dashboard.jsx 25-52 */}
      <div className="card" style={{ padding: '22px 24px', marginBottom: 18 }}>
        <div className="between" style={{ flexWrap: 'wrap', gap: 14 }}>
          <div>
            <div className="eyebrow">MAQSAD · {data.goal.by}</div>
            {/* Goal CATEGORY chip — the roadmap surfaces it; mirror it here so the main
                screen shows "what we're optimising for", not just a bare follower count. */}
            {data.goal.primaryGoal && GOAL_LABEL_UZ[data.goal.primaryGoal] && (
              <div className="row" style={{ gap: 6, marginTop: 6 }}>
                <span className="tag accent">Maqsad: {GOAL_LABEL_UZ[data.goal.primaryGoal]}</span>
                {data.goal.secondaryGoal && GOAL_LABEL_UZ[data.goal.secondaryGoal] && (
                  <span className="tag">+ {GOAL_LABEL_UZ[data.goal.secondaryGoal]}</span>
                )}
              </div>
            )}
            <div
              className="row"
              style={{ alignItems: 'baseline', gap: 12, marginTop: 8, flexWrap: 'wrap' }}
            >
              <span className="serif" style={{ fontSize: 44, lineHeight: 1 }}>
                {fmt(data.goal.current)}
              </span>
              <span className="dim mono">/</span>
              <span className="serif" style={{ fontSize: 28, color: 'var(--color-ink-3)' }}>
                {fmt(data.goal.target)}
              </span>
              <span className="tag accent">+{fmt(remaining)} qoldi</span>
            </div>
          </div>
          <div>
            <div className="eyebrow">JORIY SUR&apos;AT</div>
            <div className="serif" style={{ fontSize: 26, marginTop: 8 }}>
              {data.goal.weeklyRate >= 0 ? '+' : ''}
              {fmt(data.goal.weeklyRate)} / hafta
            </div>
            <div className="num-sub" style={{ marginTop: 6 }}>
              Maqsad sur&apos;ati: {fmt(data.goal.requiredRate)} / hafta
            </div>
          </div>
        </div>
        {/* BB20: the fill alone is invisible at 0%. Overlay a current-
            position dot (clamped to ≥1.5% so it's still visible at zero)
            so the user always sees where they stand on the journey. */}
        <div className="bar" style={{ height: 8, marginTop: 16, position: 'relative' }}>
          <span style={{ width: `${goalPct}%` }} />
          <span
            title={`Hozir: ${fmt(data.goal.current)} obunachi`}
            style={{
              position: 'absolute',
              top: '50%',
              left: `${Math.min(98, Math.max(1.5, goalPct))}%`,
              transform: 'translate(-50%, -50%)',
              width: 14,
              height: 14,
              borderRadius: 999,
              background: 'var(--color-accent)',
              border: '2px solid var(--color-bg)',
              boxShadow: '0 0 0 1px var(--color-accent)',
            }}
          />
        </div>
        <div
          className="between"
          style={{
            fontSize: 11,
            // BB20: was ink-3 (low contrast). Bump to ink-2 so the station
            // labels are actually legible against the dark card.
            color: 'var(--color-ink-2, #d1d5db)',
            marginTop: 12,
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            gap: '4px 10px',
          }}
        >
          <span className="mono" style={{ color: 'var(--color-accent)' }}>
            {fmt(data.goal.current)} · hozir
          </span>
          <span className="mono">{fmt(data.goal.target * 0.25)} · Bekat 01</span>
          <span className="mono">{fmt(data.goal.target * 0.5)} · Bekat 02</span>
          <span className="mono">{fmt(data.goal.target * 0.75)}</span>
          <span className="mono" style={{ color: 'var(--color-accent)' }}>
            {fmt(data.goal.target)} · Maqsad
          </span>
        </div>
      </div>

      {/* KPI row — auto-fit so the three cards drop to 2-up (then 1-up) as the
          content column narrows on mid-size screens, instead of staying three
          cramped ~185px cards next to the sidebar at 901-1100px. */}
      <div
        className="stagger"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 18,
          marginBottom: 18,
        }}
      >
        <KpiCard
          title="Obunachilar"
          value={fmt(data.kpis.followers.value)}
          delta={data.kpis.followers.delta30d}
          series={data.kpis.followers.series14d}
        />
        <KpiCard
          title="30 kunlik qamrov"
          value={fmt(data.kpis.reach30.value)}
          delta={data.kpis.reach30.delta30d}
          series={data.kpis.reach30.series}
        />
        <KpiCard
          title="Engagement"
          value={`${data.kpis.engagement.value}%`}
          delta={data.kpis.engagement.delta30d}
          series={data.kpis.engagement.series}
        />
      </div>

      {/* Growth chart */}
      <div className="card" style={{ marginBottom: 18 }}>
        <div className="card-head">
          <div>
            <div className="card-title">Obunachilar trayektoriyasi</div>
            <div className="card-sub">
              {/* The "+14 KUN PROGNOZ" half is only true once the forecast
                  worker has run within the last week (data.forecastReady).
                  Otherwise we promise it for later instead of claiming a
                  forecast that doesn't exist (the roadmap page already says
                  "Prognoz hali yo'q" — these two messages used to disagree). */}
              30 KUN AKTUAL ·{' '}
              {data.forecastReady
                ? '+14 KUN PROGNOZ · AGENT ENSEMBLE'
                : "PROGNOZ TO'PLANMOQDA"}
            </div>
          </div>
          <div className="row">
            {(() => {
              // Compute BOTH the number and its sign from ONE source — the real
              // 30-day snapshot series (newest - oldest) — not a static onboarding
              // figure with a separately-derived sign (which could contradict it).
              const g = data.growth;
              if (!g || g.length < 2) return null; // not enough snapshot history yet
              const d = (g[g.length - 1] ?? 0) - (g[0] ?? 0);
              return (
                <span className="tag accent">
                  {d >= 0 ? '+' : ''}
                  {fmt(d)} oxirgi 30 kun
                </span>
              );
            })()}
            {data.forecast?.accuracyPct != null && (
              <span className="tag">Forecast aniqlik · {data.forecast.accuracyPct.toFixed(0)}%</span>
            )}
          </div>
        </div>
        <GrowthChart
          data={data.growth.length > 0 ? data.growth : [data.goal.current]}
          goal={data.goal.target}
        />
      </div>

      {/* Streak + audience */}
      <div
        style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 18, marginBottom: 18 }}
      >
        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">Kontent streak</div>
              {/* BB23: the static "26 HAFTA · POST QILINGAN KUN" sub-line
                  read as a claim of 26 weeks of history even on an empty
                  grid. Gate it on hasData so a fresh account sees an
                  honest "fills after first post" line instead. */}
              <div className="card-sub">
                {data.streak.hasData
                  ? '26 HAFTA · YASHIL — POST QILINGAN KUN · INTENSIVLIK = RETENTION'
                  : "BIRINCHI POSTDAN KEYIN TO'LADI · HAR KUN BITTA KATAKCHA"}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div
                className="serif"
                style={{
                  fontSize: 36,
                  lineHeight: 1,
                  color: data.streak.today > 0 ? 'var(--color-good)' : 'var(--color-ink-4, #6b7280)',
                }}
              >
                {data.streak.today}
              </div>
              <div className="num-sub">
                {data.streak.today > 0 ? 'kun ketma-ket' : 'hali boshlanmagan'}
              </div>
            </div>
          </div>
          <div className="streak-grid">
            {data.streak.cells.map((v, i) => (
              <div
                key={i}
                className={`streak-cell l${v} ${i === data.streak.cells.length - 1 ? 'today' : ''}`}
                title={`Day ${i + 1}: intensity ${v}`}
              />
            ))}
          </div>
          <div
            className="between"
            style={{ fontSize: 11, color: 'var(--color-ink-3)', marginTop: 16 }}
          >
            <span className="mono">Kam</span>
            <div className="row" style={{ gap: 4 }}>
              <span className="streak-cell" style={{ width: 12 }} />
              <span className="streak-cell l1" style={{ width: 12 }} />
              <span className="streak-cell l2" style={{ width: 12 }} />
              <span className="streak-cell l3" style={{ width: 12 }} />
              <span className="streak-cell l4" style={{ width: 12 }} />
            </div>
            <span className="mono">Ko&apos;p</span>
            <span className="mono dim">·</span>
            {/* Companion to BB23: the trailing legend caption also claimed
                "Hafta N dan beri" history. Only show it once there's a
                real streak; otherwise invite the first post. */}
            <span className="mono">
              {data.streak.today > 0
                ? `Hafta ${Math.max(1, Math.ceil(data.streak.today / 7))} dan beri faol`
                : "Birinchi postni joylang"}
            </span>
          </div>
        </div>

        {data.audience ? (
          <div className="card">
            <div className="card-head">
              <div>
                <div className="card-title">Auditoriya</div>
                <div className="card-sub">
                  SIFAT · {audienceQualityScore(data.audience)}/100 · SEKIN O&apos;SISH OK
                </div>
              </div>
            </div>
            <div className="col" style={{ gap: 18 }}>
              <div>
                <div className="eyebrow" style={{ marginBottom: 8 }}>YOSH</div>
                <BarList items={data.audience.age} />
              </div>
              <div>
                <div className="eyebrow" style={{ marginBottom: 8 }}>TOP SHAHARLAR</div>
                <BarList items={data.audience.topCities.slice(0, 4)} accent="var(--color-warm)" />
              </div>
              <div>
                <div className="eyebrow" style={{ marginBottom: 8 }}>JINS</div>
                <div className="row" style={{ gap: 8 }}>
                  <div style={{ flex: data.audience.gender.female }}>
                    <div className="bar" style={{ height: 24, borderRadius: 6 }}>
                      <span style={{ width: '100%', background: 'var(--color-rose)' }} />
                    </div>
                    <div className="mono" style={{ fontSize: 11, marginTop: 6 }}>
                      F · {data.audience.gender.female}%
                    </div>
                  </div>
                  <div style={{ flex: data.audience.gender.male }}>
                    <div className="bar" style={{ height: 24, borderRadius: 6 }}>
                      <span style={{ width: '100%', background: 'var(--color-cool)' }} />
                    </div>
                    <div className="mono" style={{ fontSize: 11, marginTop: 6 }}>
                      M · {data.audience.gender.male}%
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="card">
            <div className="card-title">Auditoriya</div>
            <p className="muted" style={{ marginTop: 8, fontSize: 13 }}>
              Demografik ma'lumot hali to'planmagan. Account Tracker keyingi 24 soatda yangilab beradi.
            </p>
          </div>
        )}
      </div>

      <div className="divider-label">
        <span className="tx">AI Studio · jonli faollik</span>
        <span className="ln" />
      </div>

      <div
        style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 18, marginBottom: 18 }}
      >
        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">Agentlar dialogi</div>
              <div className="card-sub">
                {AGENTS.length} AGENT · OXIRGI 1 SOAT · KONTEKST · SIZNING SOHANGIZ
              </div>
            </div>
            <span className="pill">
              <span className="live-dot" />STREAMING
            </span>
          </div>
          <div className="col" style={{ gap: 0 }}>
            {data.feed.slice(0, 5).map((m, i) => (
              <div key={m.id} className="agent-row">
                <AgentAvatar kind={m.agent as AgentKind} letter={agentLetter(m.agent)} />
                <div>
                  <div className="row" style={{ gap: 10 }}>
                    <span className="agent-name">{m.role}</span>
                    <span className="agent-time">{m.minutesAgo}m oldin</span>
                    {m.important && (
                      <span className="tag accent" style={{ padding: '1px 6px', fontSize: 9 }}>
                        YANGI
                      </span>
                    )}
                  </div>
                  <div className="agent-msg">{m.content}</div>
                </div>
                <div className="thinking" style={{ alignSelf: 'center' }}>
                  {i === 0 ? (
                    <>
                      <span /> <span /> <span />
                    </>
                  ) : null}
                </div>
              </div>
            ))}
            {data.feed.length === 0 && (
              <p className="muted" style={{ fontSize: 13 }}>
                Hozircha agentlardan suhbat yo'q. Birinchi roadmap_generation run'idan keyin paydo bo'ladi.
              </p>
            )}
          </div>
        </div>

        <div className="col" style={{ gap: 18 }}>
          <div className="card">
            <div className="card-head">
              <div>
                <div className="card-title">Kontent ustunlari</div>
                <div className="card-sub">{data.pillars.length} TA PILLAR · SHU OYDAGI ULUSH</div>
              </div>
            </div>
            <div className="col">
              {data.pillars.map((p, i) => (
                <div key={p.id}>
                  <div className="between" style={{ marginBottom: 6 }}>
                    <span style={{ fontSize: 13 }}>{p.name}</span>
                    <div className="row">
                      <span className="mono dim" style={{ fontSize: 11 }}>
                        {p.sharePct}%
                      </span>
                      {/* BB26: "perf N" was an opaque acronym. Spell it out
                          as a samaradorlik percentage. */}
                      <span
                        className="tag accent"
                        title="Ushbu ustun bo'yicha kontentning o'rtacha samaradorligi"
                      >
                        Samaradorlik {(p.perfScore * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  <div className="bar">
                    <span
                      style={{
                        width: `${Math.min(100, p.sharePct * 2)}%`,
                        background: p.color
                          ? `linear-gradient(90deg, ${p.color}, ${p.color}cc)`
                          : `linear-gradient(90deg, oklch(0.66 0.24 305), oklch(0.72 0.22 ${320 + i * 10}))`,
                      }}
                    />
                  </div>
                </div>
              ))}
              {data.pillars.length === 0 && (
                <p className="muted" style={{ fontSize: 13 }}>
                  Pillars hali aniqlanmagan. Initial analysis agentni ishga tushiring.
                </p>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <div>
                <div className="card-title">Eng yaqin raqobat</div>
                <div className="card-sub">OVERLAP = ULAR BILAN BIR XIL AUDITORIYA</div>
              </div>
            </div>
            <div className="col" style={{ gap: 0 }}>
              {data.competitors.map((c) => (
                <div key={c.id} className="kpi">
                  <div className="row">
                    <span style={{ fontSize: 13 }} className="mono">
                      {c.handle}
                    </span>
                    <span className="tag">{fmt(c.followers)}</span>
                  </div>
                  <div className="row">
                    <span className="mono dim" style={{ fontSize: 11 }}>
                      overlap {c.overlapPct}%
                    </span>
                    <Delta value={c.growthRate} />
                  </div>
                </div>
              ))}
              {data.competitors.length === 0 && (
                <p className="muted" style={{ fontSize: 13 }}>
                  Raqobatchilar hali kuzatuvga qo'shilmagan.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Top posts */}
      <div className="card">
        <div className="card-head">
          <div>
            <div className="card-title">Eng yaxshi 3 ta post</div>
            <div className="card-sub">OXIRGI 30 KUN · REACH BO'YICHA</div>
          </div>
          <Link href={'/posts' as never} className="btn">Hammasini ko&apos;rish</Link>
        </div>
        <div
          className="stagger"
          style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 18 }}
        >
          {data.topPosts.map((p, i) => (
            <div
              key={p.id}
              className="card"
              style={{ background: 'var(--color-bg-elev)', padding: 14 }}
            >
              <div
                className="shot-placeholder"
                style={{ aspectRatio: '1', marginBottom: 10, overflow: 'hidden', borderRadius: 6 }}
              >
                {p.thumbnailUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={p.thumbnailUrl}
                    alt={p.title || 'Instagram post thumbnail'}
                    style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                ) : (
                  <StickFigure />
                )}
                <div
                  className="mono dim"
                  style={{ position: 'absolute', bottom: 8, left: 10, fontSize: 9 }}
                >
                  POST · {i + 1}
                </div>
              </div>
              <div className="row" style={{ marginBottom: 8 }}>
                <span className="tag">{p.type}</span>
              </div>
              <div className="serif" style={{ fontSize: 18, lineHeight: 1.1 }}>
                {p.title}
              </div>
              <div className="row" style={{ justifyContent: 'space-between', marginTop: 10 }}>
                <div className="col" style={{ gap: 2 }}>
                  <span className="num-sub">Qamrov</span>
                  <span className="mono">{fmt(p.reach)}</span>
                </div>
                <div className="col" style={{ gap: 2, alignItems: 'flex-end' }}>
                  <span className="num-sub">Saqlangan</span>
                  <span className="mono">{fmt(p.save)}</span>
                </div>
              </div>
            </div>
          ))}
          {data.topPosts.length === 0 && (
            <p className="muted" style={{ fontSize: 13 }}>
              Postlar hali kuzatuvga olinmagan.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function KpiCard({
  title,
  value,
  delta,
  series,
}: {
  title: string;
  value: string;
  // null = no prior-period data → <Delta> renders `—` instead of fake 0%.
  delta: number | null;
  series: number[];
}) {
  return (
    <div className="card">
      <div className="between" style={{ marginBottom: 16 }}>
        <div className="eyebrow">{title}</div>
        <Delta value={delta} />
      </div>
      <div className="num">{value}</div>
      <div style={{ marginTop: 16 }}>
        <Sparkline data={series.length > 0 ? series : [0, 0]} h={42} />
      </div>
    </div>
  );
}

/**
 * Audience quality score 0-100 — quick heuristic from the snapshot:
 *   gender split balance + city diversity + age coverage.
 * Result tracks "how reliable is this demographic snapshot" — used as the
 * Auditoriya card subtitle (front uses a static "78/100" string).
 */
function audienceQualityScore(audience: NonNullable<DashboardData['audience']>): number {
  const total = audience.gender.female + audience.gender.male;
  if (total === 0) return 0;
  const balance = 100 - Math.abs(audience.gender.female - audience.gender.male); // 100 if 50/50
  const cityCount = Math.min(4, audience.topCities.length) * 12; // up to 48
  const ageCount = Math.min(5, audience.age.length) * 6; // up to 30
  return Math.min(100, Math.round(balance * 0.5 + cityCount + ageCount));
}

function agentLetter(kind: string): string {
  return { market: 'M', industry: 'I', writer: 'W', audience: 'A' }[kind] ?? '?';
}

/**
 * Maps the `?ig_error=` query param from the Instagram OAuth callback to a
 * human-readable Uzbek sentence. Defaults to a generic message so any new
 * error code from Meta still produces something readable.
 */
function igErrorMessage(code: string): string {
  switch (code) {
    case 'access_denied':
    case 'user_denied':
      return "Siz Instagram ruxsatini bermadingiz.";
    case 'state_mismatch':
      return "Xavfsizlik tekshiruvi muvaffaqiyatsiz tugadi (CSRF state).";
    case 'invalid_callback':
      return "Instagram'dan to'liq javob kelmadi.";
    case 'invalid_redirect_uri':
      return "Meta App'ga ushbu redirect URI qo'shilmagan. Meta dashboard → Instagram → API setup → Valid OAuth Redirect URIs ro'yxatiga \"https://smm.brotech.uz/api/auth/callback/instagram\" qo'shing.";
    case 'scope_not_approved':
      return "Meta App'ga kerakli scope'lar (insights, comments) uchun Advanced Access yo'q. App Review submit qiling yoki o'zingizni Instagram Tester sifatida qo'shing.";
    case 'invalid_app_id':
      return "INSTAGRAM_APP_ID Coolify env'ida noto'g'ri. Meta dashboard → App Settings → Basic'dan to'g'ri ID'ni ko'chiring.";
    case 'exchange_failed':
      return "Token almashish muvaffaqiyatsiz — Meta App sozlamalarini tekshirish kerak. /api/debug/instagram orqali env'larni tekshiring.";
    case 'personal_account':
      return "Personal Instagram akkaunti qo'llab-quvvatlanmaydi — Professional rejimga o'tkazing.";
    default:
      return `Sabab: ${code}.`;
  }
}

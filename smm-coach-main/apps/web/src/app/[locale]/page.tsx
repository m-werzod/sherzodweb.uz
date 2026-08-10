/**
 * Landing page — 1-to-1 React port of front/Landing.html. Markup,
 * classNames, copy and SVG icons preserved exactly so the look matches
 * the static template. All CTAs route into the live Next.js auth pages.
 */
import Link from 'next/link';
import { FaqAccordion } from '@/components/landing/faq-accordion';

export const dynamic = 'force-dynamic';

const BRAND_SVG = (id: string) => (
  <svg width="36" height="36" viewBox="0 0 120 120" style={{ display: 'block', flexShrink: 0 }}>
    <defs>
      <linearGradient id={id} x1="0%" y1="100%" x2="100%" y2="0%">
        <stop offset="0%" stopColor="var(--brand-accent)" />
        <stop offset="100%" stopColor="var(--brand-accent-2)" />
      </linearGradient>
    </defs>
    <rect width="120" height="120" rx="28" fill={`url(#${id})`} />
    <path
      d="M 22 92 Q 50 88, 60 60 T 92 28"
      stroke="var(--brand-ink)"
      strokeWidth="6"
      fill="none"
      strokeLinecap="round"
      opacity="0.22"
    />
    <path
      d="M 80 38 Q 56 38, 56 52 Q 56 60, 70 62 Q 86 64, 86 76 Q 86 90, 62 90"
      stroke="var(--brand-ink)"
      strokeWidth="9"
      fill="none"
      strokeLinecap="round"
    />
    <circle cx="92" cy="28" r="7" fill="var(--brand-ink)" />
    <circle cx="92" cy="28" r="3.5" fill={`url(#${id})`} />
  </svg>
);

export default function LandingPage() {
  return (
    <>
      {/* NAV */}
      <nav className="lp-nav">
        <div className="lp-shell lp-nav-inner">
          <Link href="/" className="brand" style={{ textDecoration: 'none' }}>
            {BRAND_SVG('hd-landing-1')}
            <div>
              <div className="brand-name">SMM Coach</div>
              <div className="brand-sub">AI SMM STUDIO</div>
            </div>
          </Link>
          <div className="lp-nav-links">
            <a href="#works">Qanday ishlaydi</a>
            <a href="#agents">Agentlar</a>
            <a href="#pricing">Narx</a>
            <a href="#faq">FAQ</a>
          </div>
          <div className="lp-nav-cta">
            <Link href="/sign-in" className="lp-cta-secondary" style={{ padding: '8px 14px', fontSize: 13 }}>
              Kirish
            </Link>
            <Link href="/sign-up" className="lp-cta-primary" style={{ padding: '8px 16px', fontSize: 13 }}>
              Bepul boshlash
            </Link>
          </div>
        </div>
      </nav>

      {/* HERO */}
      <section className="lp-hero">
        <div className="lp-shell lp-hero-grid">
          <div>
            <div className="lp-hero-eyebrow">
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: 99,
                  background: 'var(--good)',
                  boxShadow: '0 0 0 4px color-mix(in oklch, var(--good) 20%, transparent)',
                }}
              />
              BETA · O'ZBEKISTON UCHUN
            </div>
            <h1>
              Sizning shaxsiy
              <br />
              <em>AI marketing</em>
              <br />
              jamoangiz.
            </h1>
            <p>
              Akkauntingizni ulang, maqsadingizni ayting — 10 ta AI agent tahlil qiladi, yo&apos;l
              xaritasini chizadi, har bir video uchun senariy yozadi, montaj qiladi va o&apos;zi
              joylaydi. Siz faqat oldida turing.
            </p>
            <div className="lp-hero-cta">
              <Link href="/sign-up" className="lp-cta-primary">
                Bepul boshlash <span style={{ fontFamily: 'var(--mono)' }}>→</span>
              </Link>
              <a href="#works" className="lp-cta-secondary">
                Qanday ishlaydi
              </a>
              <span className="lp-cta-note">Kredit karta kerak emas · 14 kun Pro</span>
            </div>
          </div>

          <div className="lp-hero-side">
            <div className="lp-floating-tag">
              <span className="agent-dot agent-avatar market">M</span>
              Market Analyst: <i style={{ fontStyle: 'italic' }}>UZ trendlari</i> · 2m oldin
            </div>

            <div className="lp-trajectory-card">
              <div
                style={{
                  fontFamily: 'var(--mono)',
                  fontSize: 10,
                  letterSpacing: '0.18em',
                  textTransform: 'uppercase',
                  color: 'var(--ink-3)',
                  marginBottom: 14,
                }}
              >
                Sizning yo&apos;l xaritangiz · 12 hafta
              </div>
              <div className="tj-row">
                <span className="lp-tj-current">Hozir</span>
                <span style={{ fontFamily: 'var(--mono)', color: 'var(--ink-4)' }}>→</span>
                <span className="lp-tj-target">Maqsad</span>
              </div>
              <div className="lp-tj-bar">
                <span />
              </div>

              <div className="lp-tj-mini-nodes">
                <div className="lp-tj-node done">
                  <span className="lp-tj-node-dot" />
                  <span className="lp-tj-node-text">Sohani o&apos;tkirlash</span>
                  <span className="lp-tj-node-meta">Bosqich 1</span>
                </div>
                <div className="lp-tj-node done">
                  <span className="lp-tj-node-dot" />
                  <span className="lp-tj-node-text">Hook eksperimenti</span>
                  <span className="lp-tj-node-meta">Bosqich 2</span>
                </div>
                <div className="lp-tj-node active">
                  <span className="lp-tj-node-dot" />
                  <span className="lp-tj-node-text">Birinchi viral</span>
                  <span className="lp-tj-node-meta" style={{ color: 'var(--accent)' }}>
                    Bosqich 3 · joriy
                  </span>
                </div>
                <div className="lp-tj-node">
                  <span className="lp-tj-node-dot" />
                  <span className="lp-tj-node-text">Series formati</span>
                  <span className="lp-tj-node-meta">Bosqich 4</span>
                </div>
              </div>
            </div>

            <div
              className="lp-floating-tag"
              style={{ left: 140, top: 30, transform: 'rotate(2deg)' }}
            >
              <span className="agent-dot agent-avatar writer">W</span>
              Scriptwriter: <i style={{ fontStyle: 'italic' }}>sizning ovozingizda hook</i>
            </div>
            <div
              className="lp-floating-tag"
              style={{ left: 40, top: 260, transform: 'rotate(-1deg)' }}
            >
              <span className="agent-dot agent-avatar audience">A</span>
              Audience: <i style={{ fontStyle: 'italic' }}>eng faol vaqt 19:00</i>
            </div>
          </div>
        </div>
      </section>

      {/* MARQUEE */}
      <div className="lp-marquee">
        <div className="lp-marquee-track">
          {[0, 1].map((dup) => (
            <React.Fragment key={dup}>
              <span>
                ● UZ TRENDING <i>jonli kuzatuvda</i>
              </span>
              <span>
                ● HOOK PATTERN <i>retention +1.4×</i>
              </span>
              <span>
                ● OPTIMAL PUBLISH <i>auditoriyaga moslangan vaqt</i>
              </span>
              <span>
                ● COMMENT INTENT <i>auto-aniqlash</i>
              </span>
              <span>
                ● PILLAR <i>sizning sohangiz</i> perf score
              </span>
              <span>
                ● AUDIO © <i>safe</i>
              </span>
              <span>
                ● PREDICTED REACH <i>har video uchun ±12%</i>
              </span>
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* HOW IT WORKS */}
      <section className="lp-section" id="works">
        <div className="lp-shell">
          <div className="lp-section-eyebrow">Qanday ishlaydi</div>
          <h2>
            Akkauntdan <em>auto-publish</em> gacha — 4 ta bosqich.
          </h2>
          <div className="lp-section-sub">
            Ro'yxatdan o'tasiz · 10 agent ishga tushadi · har kuni sizning ovozingiz va
            sohangiz bo'yicha ishlaydi.
          </div>

          <div className="lp-steps">
            {[
              { n: '01', t: 'Ulang', d: 'Instagram akkauntingizni 2 daqiqada ulang. AI 90 kunlik kontent va auditoriyani tahlil qiladi.' },
              { n: '02', t: 'Suhbat', d: 'Qayerda va qayerga — AI bilan 5 daqiqalik suhbatda muddat, ovoz, sohani belgilab olamiz.' },
              { n: '03', t: "Yo'l xaritasi", d: "Maqsadgacha 21+ ta topshiriq tuzilib chiqadi. Har biri to'liq video brief bilan." },
              { n: '04', t: 'Produksiya', d: 'Material yuklang · AI montaj qiladi, audio qo\'yadi, caption yozadi va o\'zi joylaydi.' },
            ].map((s) => (
              <div key={s.n} className="lp-step">
                <div className="lp-step-num">{s.n}</div>
                <div className="lp-step-arrow">→</div>
                <div className="lp-step-title">{s.t}</div>
                <div className="lp-step-desc">{s.d}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* AGENTS */}
      <section className="lp-section" id="agents" style={{ paddingTop: 0 }}>
        <div className="lp-shell">
          <div className="lp-section-eyebrow">10 AI agent</div>
          <h2>
            <em>O'nta agent</em>, bitta miya, bitta sizning ovozingiz.
          </h2>
          <div className="lp-section-sub">
            Har biri o'z faoliyatida usta. Bir-biriga gapirib turishadi. Asosiy yo'ldan chiqib
            ketmasdan, lekin tabiiy mavzular qo'shilishiga ham yo'l qo'yiladi.
          </div>

          <div className="lp-agents">
            {AGENT_CARDS.map((a) => (
              <div key={`${a.r}-${a.phase}`} className="lp-agent-card" style={{ position: 'relative' }}>
                <span className="lp-agent-phase">{a.phase}</span>
                <div
                  className={`lp-agent-av agent-avatar ${a.k}`}
                  style={{ color: 'var(--accent-ink)' }}
                >
                  <a.Icon />
                </div>
                <div>
                  <div className="lp-agent-role">{a.r}</div>
                  <div className="lp-agent-title">{a.t}</div>
                </div>
                <div className="lp-agent-desc">{a.d}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* STATS */}
      <div className="lp-shell">
        <div className="lp-stats">
          <div className="lp-stat">
            <div className="lp-stat-val">Beta</div>
            <div className="lp-stat-label">TEZ KUNLARDA ICHKI ISHLANMA</div>
          </div>
          <div className="lp-stat">
            <div className="lp-stat-val">10</div>
            <div className="lp-stat-label">AI AGENT · BIRLASHTIRILGAN</div>
          </div>
          <div className="lp-stat">
            <div className="lp-stat-val">UZ</div>
            <div className="lp-stat-label">BIRINCHI BOSQICH · O'ZBEKISTON</div>
          </div>
          <div className="lp-stat">
            <div className="lp-stat-val">14 kun</div>
            <div className="lp-stat-label">BEPUL SINOV DAVRI</div>
          </div>
        </div>
      </div>

      {/* FEATURE: ROADMAP */}
      <div className="lp-shell">
        <div className="lp-feature">
          <div>
            <div className="lp-section-eyebrow">Yo'l xaritasi</div>
            <h3>
              Maqsadgacha har bir{' '}
              <em
                style={{
                  background:
                    'linear-gradient(95deg, color-mix(in oklch, var(--accent) 70%, white), var(--accent-2))',
                  WebkitBackgroundClip: 'text',
                  backgroundClip: 'text',
                  color: 'transparent',
                  fontStyle: 'normal',
                }}
              >
                qadam
              </em>{' '}
              chiziladi.
            </h3>
            <p>
              Sizning maqsadingiz orzu emas, balki har 2-3 hafta uchun aniq topshiriqlar zanjiri.
              Har bir tugun bitta video. Bekat&apos;larda maxsus master-format&apos;lar ochiladi.
            </p>
            <p style={{ marginTop: 14 }}>
              AI har bajarilgan videodan keyin haqiqiy natijani prognoz bilan solishtirib, qolgan
              yo&apos;lni qaytadan kalibrlaydi.
            </p>
          </div>
          <div className="lp-feature-visual">
            <div
              style={{
                position: 'absolute',
                left: '50%',
                top: 0,
                bottom: 0,
                width: 1,
                background:
                  'repeating-linear-gradient(to bottom, var(--line) 0 4px, transparent 4px 8px)',
                transform: 'translateX(-50%)',
              }}
            />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14, position: 'relative' }}>
              <FeatureRoadmapRow week="HAFTA 1-2" text="Sohani o'tkirlash" side="left" status="done" />
              <FeatureRoadmapRow week="HAFTA 3-4" text="Hook eksperimenti" side="right" status="done" />
              <FeatureStation label="BEKAT 01" title="Yangi bosqich" />
              <FeatureRoadmapRow week="JORIY" text="Series formati" side="left" status="current" />
            </div>
          </div>
        </div>

        <div className="lp-feature reverse">
          <div
            className="lp-feature-visual"
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
              justifyContent: 'center',
            }}
          >
            <FeatureAgentLine
              kind="market"
              letter="M"
              text={
                <>
                  UZ region&apos;ida{' '}
                  <i style={{ fontStyle: 'italic' }}>qisqa-format + ASMR audio</i> 3.2× ko&apos;proq
                  save oladi. Sizning sohangiz uchun ham mos.
                </>
              }
            />
            <FeatureAgentLine
              kind="audience"
              letter="A"
              text={
                <>
                  Auditoriyangizdan keladigan asosiy savol turini aniqladim — caption&apos;ga{' '}
                  <i style={{ fontStyle: 'italic' }}>aniq javob</i> qo&apos;shsangiz, save +30%.
                </>
              }
            />
            <FeatureAgentLine
              kind="writer"
              letter="W"
              highlight
              text={
                <>
                  Qabul qilindi. Hook tayyor —{' '}
                  <i style={{ fontStyle: 'italic' }}>sizning ovozingizda</i>, sohangizga
                  moslangan, 3 ta variant A/B test uchun.
                </>
              }
            />
          </div>
          <div>
            <div className="lp-section-eyebrow">AI agentlar dialogi</div>
            <h3>
              Bir-biriga{' '}
              <em
                style={{
                  background:
                    'linear-gradient(95deg, color-mix(in oklch, var(--accent) 70%, white), var(--accent-2))',
                  WebkitBackgroundClip: 'text',
                  backgroundClip: 'text',
                  color: 'transparent',
                  fontStyle: 'normal',
                }}
              >
                gapirib turishadi.
              </em>
            </h3>
            <p>
              Senarist Market Analyst&apos;dan trend ma&apos;lumotini oladi, Audience
              Watcher&apos;dan auditoriya so&apos;rovini, Industry Scout&apos;dan mavzu
              fursatlarini — keyin sizning ovozingizda hook yozadi.
            </p>
            <p style={{ marginTop: 14 }}>
              Loop bilan ishlaydi: kutilgan natija → haqiqiy → solishtirish → keyingi senariyga
              ta&apos;sir. Har video bilan aniqroq ishlaydi.
            </p>
          </div>
        </div>
      </div>

      {/* PRICING */}
      <section className="lp-section" id="pricing">
        <div className="lp-shell">
          <div className="lp-section-eyebrow">Tarif rejalari</div>
          <h2>
            Bosqichma-bosqich <em>oson o&apos;sing.</em>
          </h2>
          <div className="lp-section-sub">
            Bepul boshlang, kerak bo&apos;lganda kengaytiring. Hech qachon shartnoma majburiyat
            yo&apos;q.
          </div>

          <div className="lp-pricing">
            <PricingPlan
              tier="Starter"
              price="$0"
              desc="Boshlash uchun. 1-bosqich · Tahlil va senariy."
              features={['1 Instagram akkaunt', '4 video senariysi / oy', '2 ta AI agent (Market + Writer)', "Yo'l xaritasi (cheklangan)", 'Hamjamiyat support']}
              ctaText="Bepul boshlash"
            />
            <PricingPlan
              featured
              tier="Pro"
              price="$49"
              desc="Faol ijodkorlar uchun. 1-bosqich to'liq."
              features={['1 Instagram akkaunt', "12 video / oy · to'liq brief", '4 ta AI agent · bozor + auditoriya + senariy', "Yo'l xaritasi · 1M gacha", 'A/B variantlar · prognoz aniqlik', 'Email support · 24 soat']}
              ctaText="Boshlash · 14 kun bepul"
              badge="TANLOV"
            />
            <PricingPlan
              tier="Agency"
              price="$199"
              desc="2-bosqich. To'liq avtomatik produksiya."
              features={['3 platforma (Instagram · TikTok · YouTube)', 'Cheksiz video', '10 ta AI agent (mantaj + audio + community)', 'Avtomatik joylash', 'AI comment javoblari', "Brend deal lid'lari", 'Maxsus support · 1 soat']}
              ctaText="Demo so'rash"
            />
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="lp-section" id="faq">
        <div className="lp-shell">
          <div className="lp-section-eyebrow">Tez-tez beriladigan savollar</div>
          <h2>
            <em>Bilmoqchi</em> bo&apos;lgan narsalaringiz.
          </h2>

          <FaqAccordion
            items={[
              {
                q: 'Bu mening Instagramimni xavfsiz ushlaydimi?',
                a: "Ha — biz Meta'ning rasmiy OAuth orqali ulaymiz. Parolingiz hech qachon bizda saqlanmaydi. Token'ni istalgan vaqt bekor qilishingiz mumkin.",
              },
              {
                q: "AI'lar mening ovozimni qaerdan biladi?",
                a: '90 kunlik kontentingizni tahlil qilamiz — caption tarzingiz, mavzular, ohang, post chastotasi. Suhbatda ham bevosita so\'raymiz. Vaqt o\'tishi bilan har bir feedback yangilaydi.',
              },
              {
                q: 'Senariy chiqdi-yu, lekin meni qoniqtirmasa-chi?',
                a: 'Senariyni so\'z bilan tahrirlashingiz mumkin. AI tushunadi: "boshqacha hook", "qisqaroq", "bolalarga ham mos qil". Har tahrir keyingi senariylarga ta\'sir qiladi.',
              },
              {
                q: '2-bosqich (avto produksiya) qachon chiqadi?',
                a: 'Agency tarifda hozir mavjud. Pro foydalanuvchilar uchun bosqichma-bosqich ochiladi — oldin AI Caption, keyin Trend Audio, keyin to\'liq mantaj.',
              },
              {
                q: 'Mening soham jiddiy / B2B / shifokorlik — mos keladimi?',
                a: "Ha. AI'lar har bir soha uchun alohida kalibrlanadi. Bizda go'zallik, oziq-ovqat, fitness, ta'lim, biznes coach sohalarida ijodkorlar bor.",
              },
              {
                q: 'Bekor qilish oson-mi?',
                a: "Bir bosish — tarifni har qachon to'xtatishingiz mumkin. Ma'lumotlaringizni JSON formatda eksport qilib olishingiz mumkin.",
              },
            ]}
          />
        </div>
      </section>

      {/* BIG CTA */}
      <div className="lp-shell">
        <div className="lp-bigcta">
          <div className="lp-section-eyebrow" style={{ marginBottom: 24 }}>
            Bepul boshlang
          </div>
          <h2>
            Birinchi qadamdan <em>maqsadgacha</em>.
            <br />
            Yo&apos;lda hech qachon yolg&apos;iz emassiz.
          </h2>
          <p>14 kun bepul Pro. Kredit karta kerak emas.</p>
          <Link
            href="/sign-up"
            className="lp-cta-primary"
            style={{ fontSize: 16, padding: '16px 28px' }}
          >
            Bepul boshlash <span style={{ fontFamily: 'var(--mono)' }}>→</span>
          </Link>
        </div>
      </div>

      {/* FOOTER */}
      <footer className="lp-footer">
        <div className="lp-shell">
          <div className="lp-footer-grid">
            <div>
              <div className="brand" style={{ marginBottom: 16 }}>
                {BRAND_SVG('hd-landing-2')}
                <div>
                  <div className="brand-name">SMM Coach</div>
                  <div className="brand-sub">AI SMM STUDIO · 2026</div>
                </div>
              </div>
              <p
                style={{
                  fontSize: 13.5,
                  color: 'var(--ink-3)',
                  maxWidth: 340,
                  lineHeight: 1.55,
                }}
              >
                Sizning shaxsiy AI marketing jamoangiz. O&apos;zbekistonda yaratilgan, butun jahon
                uchun.
              </p>
            </div>
            <div>
              <h4>Mahsulot</h4>
              <ul>
                <li>
                  <a href="#works">Qanday ishlaydi</a>
                </li>
                <li>
                  <a href="#agents">AI agentlar</a>
                </li>
                <li>
                  <a href="#pricing">Narx</a>
                </li>
                <li>
                  <Link href="/dashboard">Studio demo</Link>
                </li>
              </ul>
            </div>
            <div>
              <h4>Kompaniya</h4>
              <ul>
                <li>
                  <Link href="/">Bosh sahifa</Link>
                </li>
                <li>
                  <a href="#works">Qanday ishlaydi</a>
                </li>
                <li>
                  <a href="#pricing">Narxlar</a>
                </li>
                <li>
                  <a href="#faq">FAQ</a>
                </li>
              </ul>
            </div>
            <div>
              <h4>Yuridik</h4>
              <ul>
                <li>
                  <Link href="/privacy">Maxfiylik siyosati</Link>
                </li>
                <li>
                  <Link href="/terms">Foydalanish shartlari</Link>
                </li>
                <li>
                  <Link href="/data-deletion">Ma'lumotlarni o'chirish</Link>
                </li>
              </ul>
            </div>
          </div>
          <div className="lp-footer-bottom">
            <span>© 2026 SMM Coach · barcha huquqlar himoyalangan</span>
            <span>Tashkent · O&apos;zbekiston</span>
          </div>
        </div>
      </footer>
    </>
  );
}

import * as React from 'react';

function FeatureRoadmapRow({
  week,
  text,
  side,
  status,
}: {
  week: string;
  text: string;
  side: 'left' | 'right';
  status: 'done' | 'current';
}) {
  const cardCol = side === 'left' ? 1 : 3;
  const dotCol = 2;
  const dotColor = status === 'done' ? 'var(--good)' : 'var(--accent)';
  const borderColor = status === 'current' ? 'var(--accent)' : 'var(--line)';
  const labelColor = status === 'current' ? 'var(--accent)' : 'var(--ink-3)';
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 24px 1fr', alignItems: 'center' }}>
      <div
        style={{
          gridColumn: cardCol,
          padding: '10px 12px',
          background: 'var(--bg-elev)',
          border: `1px solid ${borderColor}`,
          borderRadius: 8,
          fontSize: 11,
        }}
      >
        <div
          style={{
            fontFamily: 'var(--mono)',
            fontSize: 9,
            letterSpacing: '0.1em',
            color: labelColor,
          }}
        >
          {week}
        </div>
        <div style={{ marginTop: 4, fontSize: 13 }}>{text}</div>
      </div>
      <div
        style={{
          gridColumn: dotCol,
          justifySelf: 'center',
          width: status === 'current' ? 14 : 12,
          height: status === 'current' ? 14 : 12,
          borderRadius: 99,
          border: `2px solid ${dotColor}`,
          background:
            status === 'current'
              ? 'color-mix(in oklch, var(--accent) 30%, transparent)'
              : 'transparent',
        }}
      />
    </div>
  );
}

function FeatureStation({ label, title }: { label: string; title: string }) {
  return (
    <div
      style={{
        padding: 14,
        borderRadius: 10,
        background: 'linear-gradient(135deg, color-mix(in oklch, var(--accent) 18%, transparent), transparent)',
        border: '1px solid var(--accent)',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          fontFamily: 'var(--mono)',
          fontSize: 9,
          letterSpacing: '0.18em',
          color: 'var(--accent)',
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: 'var(--display)',
          fontWeight: 500,
          fontSize: 22,
          marginTop: 4,
        }}
      >
        {title}
      </div>
    </div>
  );
}

function FeatureAgentLine({
  kind,
  letter,
  text,
  highlight,
}: {
  kind: string;
  letter: string;
  text: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div
        className={`agent-avatar ${kind}`}
        style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          fontFamily: 'var(--display)',
          fontWeight: 600,
          fontSize: 13,
        }}
      >
        {letter}
      </div>
      <div
        style={{
          flex: 1,
          padding: '10px 14px',
          background: highlight
            ? 'color-mix(in oklch, var(--accent) 12%, var(--bg-elev))'
            : 'var(--bg-elev)',
          border: highlight ? '1px dashed var(--accent)' : '1px solid var(--line)',
          borderRadius: 10,
          fontSize: 12.5,
          lineHeight: 1.4,
        }}
      >
        {text}
      </div>
    </div>
  );
}

function PricingPlan({
  tier,
  price,
  desc,
  features,
  ctaText,
  featured,
  badge,
}: {
  tier: string;
  price: string;
  desc: string;
  features: string[];
  ctaText: string;
  featured?: boolean;
  badge?: string;
}) {
  return (
    <div className={`lp-plan ${featured ? 'featured' : ''}`}>
      {badge && <div className="lp-plan-badge">{badge}</div>}
      <div className="lp-plan-tier">{tier}</div>
      <div className="lp-plan-price">
        {price} <small>/ oy</small>
      </div>
      <div className="lp-plan-desc">{desc}</div>
      <ul className="lp-plan-list">
        {features.map((f) => (
          <li key={f}>{f}</li>
        ))}
      </ul>
      <Link
        href="/sign-up"
        className={featured ? 'lp-cta-primary' : 'lp-cta-secondary'}
        style={{ width: '100%', justifyContent: 'center' }}
      >
        {ctaText}
      </Link>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Agent card icons — Lucide-style minimal SVG. One per agent so the
// landing reads as a tool palette, not a letter grid.
// ─────────────────────────────────────────────────────────────────────

type AgentIconProps = { size?: number };
const stroke = {
  width: 22 as number,
  height: 22 as number,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2.1,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true as const,
};

const IconTrendingUp = ({ size = 22 }: AgentIconProps) => (
  <svg {...stroke} width={size} height={size}>
    <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
    <polyline points="16 7 22 7 22 13" />
  </svg>
);
const IconNewspaper = ({ size = 22 }: AgentIconProps) => (
  <svg {...stroke} width={size} height={size}>
    <path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2" />
    <path d="M18 14h-8M15 18h-5M10 6h8v4h-8z" />
  </svg>
);
const IconUsers = ({ size = 22 }: AgentIconProps) => (
  <svg {...stroke} width={size} height={size}>
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);
const IconPen = ({ size = 22 }: AgentIconProps) => (
  <svg {...stroke} width={size} height={size}>
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
  </svg>
);
const IconScissors = ({ size = 22 }: AgentIconProps) => (
  <svg {...stroke} width={size} height={size}>
    <circle cx="6" cy="6" r="3" />
    <circle cx="6" cy="18" r="3" />
    <line x1="20" y1="4" x2="8.12" y2="15.88" />
    <line x1="14.47" y1="14.48" x2="20" y2="20" />
    <line x1="8.12" y1="8.12" x2="12" y2="12" />
  </svg>
);
const IconWave = ({ size = 22 }: AgentIconProps) => (
  <svg {...stroke} width={size} height={size}>
    <line x1="3" y1="12" x2="3" y2="12" />
    <line x1="7" y1="9" x2="7" y2="15" />
    <line x1="11" y1="6" x2="11" y2="18" />
    <line x1="15" y1="9" x2="15" y2="15" />
    <line x1="19" y1="11" x2="19" y2="13" />
  </svg>
);
const IconFlame = ({ size = 22 }: AgentIconProps) => (
  <svg {...stroke} width={size} height={size}>
    <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" />
  </svg>
);
const IconHash = ({ size = 22 }: AgentIconProps) => (
  <svg {...stroke} width={size} height={size}>
    <line x1="4" y1="9" x2="20" y2="9" />
    <line x1="4" y1="15" x2="20" y2="15" />
    <line x1="10" y1="3" x2="8" y2="21" />
    <line x1="16" y1="3" x2="14" y2="21" />
  </svg>
);
const IconUpload = ({ size = 22 }: AgentIconProps) => (
  <svg {...stroke} width={size} height={size}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);
const IconMessage = ({ size = 22 }: AgentIconProps) => (
  <svg {...stroke} width={size} height={size}>
    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
  </svg>
);

type AgentCard = {
  phase: string;
  k: 'market' | 'industry' | 'audience' | 'writer' | 'editor' | 'audio' | 'trend' | 'caption' | 'publisher' | 'community';
  r: string;
  t: string;
  d: string;
  Icon: (p: AgentIconProps) => React.JSX.Element;
};

const AGENT_CARDS: AgentCard[] = [
  { phase: 'FAZA 1 · TAHLIL', k: 'market', Icon: IconTrendingUp, r: 'Market Analyst', t: 'Bozor tahlilchisi', d: "UZ trendlari, hook patternlari, audio'lar va viral postlarning ortidagi formula." },
  { phase: 'FAZA 1 · TAHLIL', k: 'industry', Icon: IconNewspaper, r: 'Industry Scout', t: 'Soha kuzatuvchisi', d: "Sizning sohangizdagi yangiliklarni o'qiydi. Mavsumiy mavzular va imkoniyatlarni topadi." },
  { phase: 'FAZA 1 · TAHLIL', k: 'audience', Icon: IconUsers, r: 'Audience Watcher', t: 'Auditoriya kuzatuvchisi', d: "Folloverlar reaksiyasi, sentiment, retention — barchasini o'zlashtirib boradi." },
  { phase: 'FAZA 1 · SENARIY', k: 'writer', Icon: IconPen, r: 'Scriptwriter', t: 'Senariy yozuvchisi', d: "3 ta agent ma'lumotini birlashtirib, sizning ovozingizda senariy yozadi." },
  { phase: 'FAZA 2 · MANTAJ', k: 'editor', Icon: IconScissors, r: 'Video Editor', t: 'Mantajchi', d: "Xom materialni kesadi, B-roll qo'yadi, ritmni audio'ga moslaydi." },
  { phase: 'FAZA 2 · AUDIO', k: 'audio', Icon: IconWave, r: 'Audio Engineer', t: 'Audio muhandisi', d: 'Ovozni tozalaydi, EQ va kompressiya, Instagram uchun -3.2 LUFS.' },
  { phase: 'FAZA 2 · TREND', k: 'trend', Icon: IconFlame, r: 'Trend Hunter', t: 'Audio trend ovchisi', d: "Trenddagi audio'larni topadi, contentga score qiladi, eng mos variantni tanlaydi." },
  { phase: 'FAZA 2 · MATN', k: 'caption', Icon: IconHash, r: 'Caption Writer', t: 'Caption + sub', d: "Caption, subtitr va hashtag — 4 ta tilda. Auditoriya so'rovi bilan moslashadi." },
  { phase: 'FAZA 2 · JOYLASH', k: 'publisher', Icon: IconUpload, r: 'Publisher', t: 'Joylash agenti', d: "Optimal vaqtni topadi, hashtag'larni qo'yadi va Instagram'ga o'zi joylaydi." },
  { phase: 'FAZA 2 · KOMMUNITY', k: 'community', Icon: IconMessage, r: 'Community Manager', t: 'Komment menejeri', d: "Comment'larga sizning ovozingizda javob beradi. Spam'ni filtrlaydi. Siz tasdiqlaysiz." },
];

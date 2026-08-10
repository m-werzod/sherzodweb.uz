import { Link } from '@/i18n/routing';

export const metadata = {
  title: 'Tarif rejalari · SMM Coach',
  description: 'Free / Pro / Premium tariflar. Payme orqali UZ to\'lov.',
};

const TIERS = [
  {
    id: 'free',
    name: 'Free',
    priceUsd: '0',
    priceUzs: '0',
    blurb: '1 ta roadmap, 3 ta script qayta yozish',
    features: [
      'Bitta yo\'l xaritasi',
      "10 ta script avtomat (Claude Sonnet)",
      '3 ta qayta yozish chegarasi',
      'ElevenLabs ovoz (cheklangan)',
      'Imagen 3 thumbnail',
      'Email yordam',
    ],
    cta: { label: 'Bepul boshlash', href: '/sign-up' },
    accent: false,
  },
  {
    id: 'pro',
    name: 'Pro',
    priceUsd: '39',
    priceUzs: '500 000',
    blurb: 'Aktiv kontent yaratuvchilarga',
    features: [
      'CHEKSIZ roadmap qayta tuzish',
      "CHEKSIZ script + qayta yozish (Claude Opus 4)",
      'Voice cloning (sizning ovozingiz)',
      'IG OAuth + advanced insights',
      'AI competitor tracking',
      'Telegram/email prioritet yordam',
    ],
    cta: { label: 'Pro\'ni tanlash', href: '/sign-up?plan=pro' },
    accent: true,
  },
  {
    id: 'premium',
    name: 'Premium',
    priceUsd: '99',
    priceUzs: '1 250 000',
    blurb: "B'log/biznes uchun to'liq",
    features: [
      'Pro\'dagi hammasi',
      "HeyGen Avatar IV talking-head video (15 daq/oy)",
      'Runway Gen-3 B-roll generatsiyasi',
      'OpenAI Whisper transcription (cheksiz)',
      'White-label brand voice',
      "1-1 onboarding qo'ng'iroq",
    ],
    cta: { label: 'Premium', href: '/sign-up?plan=premium' },
    accent: false,
  },
];

export default function PricingPage() {
  return (
    <div style={{ maxWidth: 1100, margin: '40px auto', padding: '0 24px 80px' }}>
      <div style={{ textAlign: 'center', marginBottom: 40 }}>
        <div className="eyebrow">TARIF REJALARI</div>
        <h1 style={{ fontSize: 36, marginTop: 8, fontWeight: 700 }}>
          AI marketing jamoangiz —{' '}
          <em style={{ background: 'linear-gradient(90deg, var(--accent), var(--accent-2))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            arzonroq baholash
          </em>
        </h1>
        <p className="muted" style={{ fontSize: 15, maxWidth: 620, margin: '12px auto 0' }}>
          Har tarif Payme orqali oylik to'lanadi. Istalgan vaqt bekor qilish mumkin.
        </p>
      </div>

      <div
        style={{
          display: 'grid',
          // min(280px, 100%) lets a single card shrink below 280px on narrow
          // phones instead of forcing a horizontal scroll under ~552px.
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(280px, 100%), 1fr))',
          gap: 18,
        }}
      >
        {TIERS.map((t) => (
          <div
            key={t.id}
            className="card"
            style={{
              padding: 28,
              borderColor: t.accent ? 'var(--color-accent)' : undefined,
              background: t.accent
                ? 'color-mix(in oklch, var(--color-accent) 6%, var(--color-surface))'
                : undefined,
              position: 'relative',
            }}
          >
            {t.accent && (
              <span
                style={{
                  position: 'absolute',
                  top: -10,
                  right: 20,
                  background: 'var(--color-accent)',
                  color: 'white',
                  fontSize: 10,
                  padding: '4px 10px',
                  borderRadius: 999,
                  fontWeight: 600,
                  letterSpacing: 1,
                }}
              >
                TAVSIYA QILAMIZ
              </span>
            )}
            <div style={{ fontSize: 14, fontWeight: 600, letterSpacing: 1 }}>{t.name.toUpperCase()}</div>
            <div style={{ marginTop: 14 }}>
              <span style={{ fontSize: 40, fontWeight: 700 }}>${t.priceUsd}</span>
              <span className="muted" style={{ fontSize: 14, marginLeft: 6 }}>/oy</span>
            </div>
            <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
              ≈ {t.priceUzs} so'm
            </div>
            <div className="muted" style={{ fontSize: 13, marginTop: 14, marginBottom: 18 }}>
              {t.blurb}
            </div>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: 13, lineHeight: 1.8 }}>
              {t.features.map((f) => (
                <li key={f} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                  <span style={{ color: 'var(--color-good, #10B981)', flexShrink: 0 }}>✓</span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            <Link
              href={t.cta.href as never}
              className={t.accent ? 'btn primary' : 'btn'}
              style={{ marginTop: 22, width: '100%', display: 'block', textAlign: 'center' }}
            >
              {t.cta.label}
            </Link>
          </div>
        ))}
      </div>

      <div className="muted" style={{ textAlign: 'center', marginTop: 30, fontSize: 12 }}>
        Savollar bormi? Telegram:{' '}
        <a href="https://t.me/matsalayev" style={{ color: 'var(--color-accent)' }}>
          @matsalayev
        </a>
      </div>
    </div>
  );
}

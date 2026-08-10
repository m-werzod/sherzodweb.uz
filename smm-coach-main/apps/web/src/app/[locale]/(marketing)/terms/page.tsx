import { Link } from '@/i18n/routing';

export const metadata = {
  title: 'Terms of Service · SMM Coach',
  description: 'The terms governing your use of SMM Coach.',
};

const UPDATED = 'May 30, 2026';

const wrap: React.CSSProperties = {
  maxWidth: 820,
  margin: '0 auto',
  padding: '48px 22px 80px',
  color: 'var(--color-ink-1)',
  lineHeight: 1.7,
  fontSize: 15,
};
const h2: React.CSSProperties = { fontSize: 20, marginTop: 34, marginBottom: 8, fontWeight: 600 };

export default function TermsPage() {
  return (
    <main style={wrap}>
      <Link href="/" style={{ fontSize: 13, color: 'var(--color-accent)' }}>← SMM Coach</Link>
      <h1 style={{ fontSize: 32, marginTop: 14, fontWeight: 700 }}>Terms of Service</h1>
      <p style={{ color: 'var(--color-muted-foreground)', fontSize: 13 }}>Last updated: {UPDATED}</p>

      <h2 style={h2}>1. Acceptance</h2>
      <p>By creating an account or using SMM Coach (the &quot;Service&quot;) you agree to these Terms.
        If you do not agree, do not use the Service.</p>

      <h2 style={h2}>2. The Service</h2>
      <p>SMM Coach is an AI assistant that analyzes your Instagram account and generates a personalized
        content roadmap, scripts, and growth recommendations. Outputs are suggestions, not guarantees.</p>

      <h2 style={h2}>3. Your account</h2>
      <p>You are responsible for safeguarding your credentials and for activity under your account. You must
        provide accurate information and be authorized to connect any Instagram account you link.</p>

      <h2 style={h2}>4. Instagram &amp; acceptable use</h2>
      <p>You must comply with Instagram&apos;s and Meta&apos;s Platform Terms and Community Guidelines. You
        may not use the Service to spam, harass, scrape third-party data unlawfully, or violate any law.
        We act only on data and actions you authorize.</p>

      <h2 style={h2}>5. Payments</h2>
      <p>Paid plans are billed via Payme (Uzbekistan). Fees, limits, and features are shown on the Pricing
        page. Unless required by law, payments are non-refundable once a billing period begins.</p>

      <h2 style={h2}>6. Your content</h2>
      <p>You retain ownership of your Instagram content and of the scripts you produce. You grant us a
        limited license to process your data solely to provide the Service.</p>

      <h2 style={h2}>7. Disclaimers</h2>
      <p>The Service is provided &quot;as is&quot;. We do not guarantee any specific follower growth,
        reach, or business result. AI output may contain errors — review before acting.</p>

      <h2 style={h2}>8. Limitation of liability</h2>
      <p>To the maximum extent permitted by law, SMM Coach and BroTech are not liable for indirect or
        consequential damages, or for losses arising from your use of AI-generated suggestions.</p>

      <h2 style={h2}>9. Termination</h2>
      <p>You may stop using the Service and delete your account at any time. We may suspend accounts that
        violate these Terms or abuse the platform.</p>

      <h2 style={h2}>10. Changes</h2>
      <p>We may update these Terms; continued use after changes constitutes acceptance.</p>

      <h2 style={h2}>11. Contact</h2>
      <p><b>support@brotech.uz</b></p>

      <p style={{ marginTop: 30 }}>
        <Link href="/privacy" style={{ color: 'var(--color-accent)' }}>Privacy Policy</Link>
        {'  ·  '}
        <Link href="/data-deletion" style={{ color: 'var(--color-accent)' }}>Data Deletion</Link>
      </p>
    </main>
  );
}

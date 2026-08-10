import { Link } from '@/i18n/routing';

export const metadata = {
  title: 'Data Deletion · SMM Coach',
  description: 'How to delete your data from SMM Coach.',
};

const wrap: React.CSSProperties = {
  maxWidth: 820,
  margin: '0 auto',
  padding: '48px 22px 80px',
  color: 'var(--color-ink-1)',
  lineHeight: 1.7,
  fontSize: 15,
};
const h2: React.CSSProperties = { fontSize: 20, marginTop: 30, marginBottom: 8, fontWeight: 600 };

export default async function DataDeletionPage({
  searchParams,
}: {
  searchParams: Promise<{ code?: string }>;
}) {
  const { code } = await searchParams;

  return (
    <main style={wrap}>
      <Link href="/" style={{ fontSize: 13, color: 'var(--color-accent)' }}>← SMM Coach</Link>
      <h1 style={{ fontSize: 32, marginTop: 14, fontWeight: 700 }}>Data Deletion</h1>

      {code && (
        <div
          style={{
            marginTop: 16,
            padding: '14px 16px',
            borderRadius: 10,
            border: '1px solid var(--color-good, #19c37d)',
            background: 'color-mix(in oklab, var(--color-good, #19c37d) 12%, transparent)',
          }}
        >
          <b>Your data deletion request has been received and processed.</b>
          <div style={{ fontSize: 13, marginTop: 4, color: 'var(--color-muted-foreground)' }}>
            Confirmation code: <code>{code}</code>
          </div>
        </div>
      )}

      <p style={{ marginTop: 18 }}>
        You can delete all data SMM Coach holds about you and your Instagram account at any time.
      </p>

      <h2 style={h2}>Option 1 — Remove the app from Instagram</h2>
      <p>Go to Instagram → Settings → Apps and Websites → remove &quot;SMM Coach&quot;. Meta notifies us
        automatically and we erase all data tied to your Instagram account (profile, media, insights,
        comments, generated roadmap and scripts).</p>

      <h2 style={h2}>Option 2 — Delete in the app</h2>
      <p>Sign in, open Settings, and choose to delete your account. This removes your account and all
        associated data immediately.</p>

      <h2 style={h2}>Option 3 — Email us</h2>
      <p>Send a request from your registered email to <b>support@brotech.uz</b> and we will delete your
        data within 30 days.</p>

      <h2 style={h2}>What gets deleted</h2>
      <p>Your profile, onboarding data, connected Instagram account and tokens, mirrored media, insights,
        comments, generated roadmaps, scripts, agent messages, and analytics — everything tied to your
        tenant. Aggregated, non-identifying trend data used to seed niche knowledge is not linked to you
        and is retained.</p>

      <p style={{ marginTop: 30 }}>
        <Link href="/privacy" style={{ color: 'var(--color-accent)' }}>Privacy Policy</Link>
        {'  ·  '}
        <Link href="/terms" style={{ color: 'var(--color-accent)' }}>Terms of Service</Link>
      </p>
    </main>
  );
}

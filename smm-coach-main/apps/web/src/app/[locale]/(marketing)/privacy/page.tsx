import { Link } from '@/i18n/routing';

export const metadata = {
  title: 'Privacy Policy · SMM Coach',
  description: 'How SMM Coach collects, uses, and protects your data, including Instagram data accessed via the Meta Graph API.',
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
const li: React.CSSProperties = { marginBottom: 6 };

export default function PrivacyPage() {
  return (
    <main style={wrap}>
      <Link href="/" style={{ fontSize: 13, color: 'var(--color-accent)' }}>← SMM Coach</Link>
      <h1 style={{ fontSize: 32, marginTop: 14, fontWeight: 700 }}>Privacy Policy</h1>
      <p style={{ color: 'var(--color-muted-foreground)', fontSize: 13 }}>Last updated: {UPDATED}</p>

      <p style={{ marginTop: 18 }}>
        SMM Coach (&quot;we&quot;, &quot;us&quot;), operated by BroTech and available at
        smm.brotech.uz, is an AI-powered Instagram growth assistant. This policy explains
        what data we collect, how we use it, who we share it with, and how you can delete it.
      </p>

      <h2 style={h2}>1. Information we collect</h2>
      <ul>
        <li style={li}><b>Account data</b> — your name, email, password hash, and locale when you register.</li>
        <li style={li}><b>Onboarding data</b> — your declared field/area, target audience, current and goal follower counts, and content preferences.</li>
        <li style={li}><b>Instagram data (via the Meta Graph API, with your consent)</b> — your Instagram Business/Creator profile (username, name, biography, profile picture, follower/following/media counts), your media (posts, captions, thumbnails), media insights (reach, saves, shares, views), audience demographics (age, gender, city ranges), and comments on your posts.</li>
        <li style={li}><b>Usage data</b> — task progress, generated scripts, and product analytics.</li>
      </ul>

      <h2 style={h2}>2. How we use your data</h2>
      <ul>
        <li style={li}>Generate a personalized content roadmap and scripts for your account.</li>
        <li style={li}>Analyze your performance and audience to give growth recommendations.</li>
        <li style={li}>Track progress toward your stated follower goal.</li>
        <li style={li}>Operate, secure, and improve the service.</li>
      </ul>

      <h2 style={h2}>3. Instagram / Meta permissions</h2>
      <p>We request only the permissions needed to deliver the coaching features:</p>
      <ul>
        <li style={li}><code>instagram_business_basic</code> — read your profile and media to build your roadmap.</li>
        <li style={li}><code>instagram_business_manage_insights</code> — read reach/saves/audience insights to measure progress and forecast growth.</li>
        <li style={li}><code>instagram_business_manage_comments</code> — read comments so the assistant can suggest replies and gauge sentiment.</li>
        <li style={li}><code>instagram_business_content_publish</code> — (optional, future) publish content you explicitly approve.</li>
      </ul>
      <p>We never post or comment without your explicit action. Access tokens are stored encrypted at rest.</p>

      <h2 style={h2}>4. Third-party processors</h2>
      <p>To generate content and analyses we send the minimum necessary text to AI providers:
        Anthropic (Claude), OpenAI, Google (Gemini), Groq, and Voyage AI (embeddings). We also use
        infrastructure providers for hosting, object storage, and email, and Payme for payments. These
        processors handle data under their own terms and only to provide their service to us.</p>

      <h2 style={h2}>5. Data retention</h2>
      <p>We keep your data while your account is active. Instagram tokens expire after ~60 days and are
        refreshed only while you remain connected. You can disconnect Instagram or delete your account
        at any time (see below).</p>

      <h2 style={h2}>6. Deleting your data</h2>
      <p>You can request deletion in three ways:</p>
      <ul>
        <li style={li}>Remove the app from your Instagram settings — Meta notifies us and we erase all data tied to your Instagram account automatically.</li>
        <li style={li}>Use the in-app account deletion (Settings).</li>
        <li style={li}>Email us (below).</li>
      </ul>
      <p>See our <Link href="/data-deletion" style={{ color: 'var(--color-accent)' }}>Data Deletion instructions</Link> for details.</p>

      <h2 style={h2}>7. Security</h2>
      <p>Data is encrypted in transit (HTTPS). OAuth tokens are encrypted at rest. Access is scoped per
        tenant so one user can never read another&apos;s data.</p>

      <h2 style={h2}>8. Children</h2>
      <p>SMM Coach is not directed to anyone under 13 (or the minimum age in your jurisdiction).</p>

      <h2 style={h2}>9. Changes</h2>
      <p>We may update this policy; material changes will be posted here with a new &quot;Last updated&quot; date.</p>

      <h2 style={h2}>10. Contact</h2>
      <p>Questions or data requests: <b>support@brotech.uz</b></p>

      <p style={{ marginTop: 30 }}>
        <Link href="/terms" style={{ color: 'var(--color-accent)' }}>Terms of Service</Link>
        {'  ·  '}
        <Link href="/data-deletion" style={{ color: 'var(--color-accent)' }}>Data Deletion</Link>
      </p>
    </main>
  );
}

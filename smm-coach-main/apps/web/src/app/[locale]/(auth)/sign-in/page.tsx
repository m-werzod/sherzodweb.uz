/**
 * Sign-in — 1-to-1 React port of front/Login.html. Left form + right
 * social-proof column with live agent mini-feed and testimonial.
 * Email/password goes through Auth.js credentials; Instagram + Google
 * buttons wire into Auth.js OAuth (Instagram falls back to chat sign-up
 * while Meta App Review is pending).
 */
import * as React from 'react';
import Link from 'next/link';
import { AuthError } from 'next-auth';
import { redirect } from 'next/navigation';
import { signIn } from '@/lib/auth/auth';
import { GoogleIcon, InstagramIcon } from '@/components/brand/instagram-icon';

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

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  // `?stale=1` is set by the dashboard layout when a session's tenant no longer
  // exists (the JWT outlived an orphan-cleaned account) — surface it as a
  // friendly banner via the same channel as auth errors.
  const authError =
    (typeof params.error === 'string' ? params.error : null) ??
    (params.stale === '1' ? 'SessionExpired' : null);

  // The adapter throws NewUserOnSignInError when an unknown Google user
  // hits /sign-in. Auth.js v5 surfaces that as OAuthCreateAccount. Bounce
  // them to /sign-up so they explicitly register.
  if (
    authError === 'OAuthCreateAccount' ||
    authError === 'AccessDenied' ||
    authError === 'CallbackRouteError'
  ) {
    redirect('/sign-up?from=google_new_user');
  }

  return (
    <div className="auth-login-shell">
      {/* LEFT */}
      <div className="auth-left">
        <div className="auth-top">
          <Link href="/" className="brand" style={{ textDecoration: 'none' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {BRAND_SVG('hd-login-1')}
              <div>
                <div className="brand-name">SMM Coach</div>
              </div>
            </div>
          </Link>
          <Link href="/">← Bosh sahifa</Link>
        </div>

        <div className="auth-body">
          <div className="auth-eyebrow">KIRISH</div>
          <h1 className="auth-title">
            Qaytib <em>kelganingiz</em> uchun rahmat.
          </h1>
          <div className="auth-sub">
            Studio sizni kutib turibdi. Joriy senariy 86% tayyor.
          </div>

          {authError && (
            <div
              style={{
                padding: '10px 14px',
                marginBottom: 18,
                fontSize: 13,
                background: 'color-mix(in oklch, var(--bad) 14%, var(--surface))',
                border: '1px solid color-mix(in oklch, var(--bad) 35%, var(--line))',
                borderRadius: 10,
                color: 'var(--ink)',
              }}
            >
              {authError === 'CredentialsSignin'
                ? "Email yoki parol noto'g'ri. Qayta urinib ko'ring."
                : authError === 'OAuthAccountNotLinked'
                  ? "Bu email allaqachon parol bilan ro'yxatdan o'tgan. Google/Instagram o'rniga, pastdagi forma orqali email va parolingiz bilan kiring."
                  : authError === 'SessionExpired'
                    ? "Sessiyangiz muddati tugagan yoki hisob yangilangan. Iltimos, qaytadan kiring."
                    : `Kirish ishlamadi: ${authError}`}
            </div>
          )}

          <form
            className="auth-form"
            action={async (formData) => {
              'use server';
              // Auth.js v5 throws `AuthError` when credentials don't match.
              // In a Server Action that error otherwise propagates to the
              // global error.tsx boundary and the user sees the "biroz
              // qoqildi" card instead of an inline message. Catch the auth
              // error specifically, redirect back with a query param the
              // page reads as `authError`, and re-throw anything else
              // (notably the synthetic redirect() throw on success).
              try {
                await signIn('credentials', {
                  email: formData.get('email'),
                  password: formData.get('password'),
                  redirectTo: '/dashboard',
                });
              } catch (err) {
                if (err instanceof AuthError) {
                  redirect(`/sign-in?error=${err.type ?? 'CredentialsSignin'}`);
                }
                throw err;
              }
            }}
          >
            <div className="field">
              <label htmlFor="email">EMAIL</label>
              <div className="field-wrap">
                <span className="field-icon">@</span>
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  placeholder="siz@misol.uz"
                />
              </div>
            </div>

            <div className="field">
              <div className="field-row">
                <label htmlFor="password">PAROL</label>
                <Link href="/forgot-password">Esdan chiqdimi?</Link>
              </div>
              <div className="field-wrap">
                <span className="field-icon">●</span>
                <input
                  id="password"
                  name="password"
                  type="password"
                  required
                  minLength={8}
                  placeholder="••••••••"
                />
              </div>
            </div>

            <button className="auth-submit" type="submit">
              Studio&apos;ga kirish <span style={{ fontFamily: 'var(--mono)' }}>→</span>
            </button>
          </form>

          <div className="auth-divider">YOKI</div>

          <div className="auth-oauth">
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
            <a href="/api/auth/instagram/start?mode=signin">
              <span className="ig-icon">
                <InstagramIcon />
              </span>
              Instagram bilan kirish
            </a>
            <form
              action={async () => {
                'use server';
                // Google OAuth auto-registers if the visitor is new — same
                // behaviour as /sign-up. No auth_intent cookie needed.
                try {
                  await signIn('google', { redirectTo: '/dashboard' });
                } catch (err) {
                  if (err instanceof AuthError) {
                    redirect(`/sign-in?error=${err.type ?? 'OAuthSignin'}`);
                  }
                  throw err;
                }
              }}
            >
              <button type="submit">
                <GoogleIcon />
                Google bilan kirish
              </button>
            </form>
          </div>

          <div className="auth-bottom">
            Hisobingiz yo&apos;qmi?{' '}
            <Link href="/sign-up">Ro&apos;yxatdan o&apos;tish</Link> — bepul.
          </div>
        </div>

        <div className="auth-foot">
          <span>© {new Date().getFullYear()} SMM COACH</span>
          <div>
            <a>Maxfiylik</a>
            <a>Foydalanish shartlari</a>
          </div>
        </div>
      </div>

      {/* RIGHT */}
      <div className="auth-right">
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              fontFamily: 'var(--mono)',
              fontSize: 11,
              letterSpacing: '0.15em',
              color: 'var(--ink-3)',
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: 99,
                background: 'var(--good)',
              }}
            />
            LIVE — 3 AGENT SIZ UCHUN ISHLAMOQDA
          </div>
        </div>

        <div>
          <div className="quote">
            &quot;Birinchi 3 haftada kontent strategiyam to'liq o'zgardi — endi har kuni nima ekanini aniq bilaman.&quot;
          </div>
          <div className="quote-by">
            <div className="quote-av">A</div>
            <div>
              <div className="quote-name">Aziza Karimova</div>
              <div className="quote-handle">@aziza.kitchen · Oziq-ovqat blogger</div>
            </div>
          </div>
        </div>

        <div className="mini-feed">
          <MiniMsg
            kind="market"
            letter="M"
            who="Market Analyst"
            time="hozir"
            text={`Bugun ertalab "tezpishir" mavzusi 4.1× ko'tarildi. Sizning sohangizga mos. Pillar 1 ga kandidat.`}
          />
          <MiniMsg
            kind="writer"
            letter="W"
            who="Scriptwriter"
            time="2m oldin"
            text={`Episode 14 senariysining 3-versiyasi tayyor. Hook A/B test prognozi: variant A 12% retention'da yaxshi.`}
          />
          <MiniMsg
            kind="audience"
            letter="A"
            who="Audience Watcher"
            time="5m oldin"
            text={`Oxirgi reel'da 71% comment "narxi" so'rab. Caption'ga ~85,000 so'm yozsangiz natija oshadi.`}
          />
        </div>
      </div>
    </div>
  );
}

function MiniMsg({
  kind,
  letter,
  who,
  time,
  text,
}: {
  kind: string;
  letter: string;
  who: string;
  time: string;
  text: string;
}) {
  return (
    <div className="mini-msg">
      <div
        className={`mini-av agent-avatar ${kind}`}
        style={{ width: 28, height: 28, borderRadius: 7, fontSize: 12 }}
      >
        {letter}
      </div>
      <div>
        <div className="mini-meta">
          {who} · {time}
        </div>
        <div className="mini-text">{text}</div>
      </div>
    </div>
  );
}

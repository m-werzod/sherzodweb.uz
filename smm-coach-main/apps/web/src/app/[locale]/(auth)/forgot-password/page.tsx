'use client';

/**
 * Forgot password — simple email-based reset request.
 *
 * Phase 3 fix: previously the sign-in page linked "Esdan chiqdimi?"
 * to /sign-up (registration). Now it links here.
 *
 * Client Component: this page uses useState + form handlers. Without the
 * 'use client' directive Next.js treats it as a Server Component and SSR
 * crashes with "e.useState is not a function" (seen in prod logs). Mirrors
 * the reset-password page; route-segment config (`export const dynamic`) is
 * intentionally omitted — it is not supported in client component pages.
 */
import * as React from 'react';
import Link from 'next/link';

export default function ForgotPasswordPage() {
  const [email, setEmail] = React.useState('');
  const [status, setStatus] = React.useState<'idle' | 'loading' | 'ok' | 'err'>('idle');
  const [msg, setMsg] = React.useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setStatus('loading');
    try {
      const res = await fetch('/api/auth/forgot-password', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const json = await res.json();
      if (res.ok) {
        setStatus('ok');
        setMsg(json.message ?? "Email jo'natildi. Qutini tekshiring.");
      } else {
        setStatus('err');
        setMsg(json.error ?? "Xatolik yuz berdi.");
      }
    } catch {
      setStatus('err');
      setMsg('Tarmoq xatoligi. Qayta urinib ko\'ring.');
    }
  };

  return (
    <div className="auth-login-shell">
      <div className="auth-left">
        <div className="auth-top">
          <Link href="/" className="brand" style={{ textDecoration: 'none' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div className="brand-name">SMM Coach</div>
            </div>
          </Link>
          <Link href="/">← Bosh sahifa</Link>
        </div>

        <div className="auth-body">
          <div className="auth-eyebrow">PAROLNI TIKLASH</div>
          <h1 className="auth-title">
            <em>Esdan chiqdimi?</em>
          </h1>
          <div className="auth-sub">
            Email manzilingizni kiriting. Agar hisob mavjud bo‘lsa, tiklash havolasini jo‘natamiz.
          </div>

          {status === 'ok' ? (
            <div
              className="card"
              style={{
                padding: '16px 18px',
                background: 'color-mix(in oklch, var(--color-good) 10%, var(--color-surface))',
                borderColor: 'var(--color-good)',
              }}
            >
              <div style={{ fontSize: 14, lineHeight: 1.5 }}>{msg}</div>
              <div style={{ marginTop: 14 }}>
                <Link href="/sign-in" className="btn primary" style={{ display: 'inline-block' }}>
                  Kirish sahifasiga qaytish
                </Link>
              </div>
            </div>
          ) : (
            <form className="auth-form" onSubmit={submit}>
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
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
              </div>

              {status === 'err' && (
                <div
                  style={{
                    padding: '10px 14px',
                    marginBottom: 18,
                    fontSize: 13,
                    background: 'color-mix(in oklch, var(--bad) 14%, var(--surface))',
                    border: '1px solid color-mix(in oklch, var(--bad) 35%, var(--line))',
                    borderRadius: 10,
                  }}
                >
                  {msg}
                </div>
              )}

              <button className="auth-submit" type="submit" disabled={status === 'loading'}>
                {status === 'loading' ? 'Yuborilmoqda…' : 'Tiklash havolasini yuborish'}
              </button>
            </form>
          )}

          <div className="auth-bottom">
            <Link href="/sign-in">← Kirish</Link>
            {' · '}
            <Link href="/sign-up">Ro‘yxatdan o‘tish</Link>
          </div>
        </div>
      </div>
    </div>
  );
}

'use client';

/**
 * Reset password — consumed from the email link.
 *
 * Expects ?token=... in the URL. Verifies the token against the
 * Account table (provider='reset-token') and updates the password.
 */
import * as React from 'react';
import { Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="auth-login-shell">
        <div className="auth-left">
          <div className="auth-body" style={{ textAlign: 'center', paddingTop: 60 }}>
            <div className="thinking" style={{ justifyContent: 'center' }}>
              <span />
              <span />
              <span />
            </div>
            <div className="mono dim" style={{ marginTop: 16, fontSize: 12 }}>
              Yuklanmoqda...
            </div>
          </div>
        </div>
      </div>
    }>
      <ResetPasswordForm />
    </Suspense>
  );
}

function ResetPasswordForm() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get('token');

  const [password, setPassword] = React.useState('');
  const [confirm, setConfirm] = React.useState('');
  const [status, setStatus] = React.useState<'idle' | 'loading' | 'ok' | 'err'>('idle');
  const [msg, setMsg] = React.useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      setStatus('err');
      setMsg('Tiklash kodi yo‘q. Qayta so‘rang.');
      return;
    }
    if (password.length < 8) {
      setStatus('err');
      setMsg('Parol kamida 8 ta belgidan iborat bo‘lishi kerak.');
      return;
    }
    if (password !== confirm) {
      setStatus('err');
      setMsg('Parollar mos kelmayapti.');
      return;
    }

    setStatus('loading');
    try {
      const res = await fetch('/api/auth/reset-password', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ token, password }),
      });
      const json = await res.json();
      if (res.ok) {
        setStatus('ok');
        setMsg(json.message ?? 'Parol yangilandi.');
        setTimeout(() => router.push('/sign-in'), 2000);
      } else {
        setStatus('err');
        setMsg(json.error ?? 'Xatolik yuz berdi.');
      }
    } catch {
      setStatus('err');
      setMsg('Tarmoq xatoligi.');
    }
  };

  if (!token) {
    return (
      <div className="auth-login-shell">
        <div className="auth-left">
          <div className="auth-body">
            <div className="auth-eyebrow">XATOLIK</div>
            <h1 className="auth-title">Tiklash kodi yo‘q</h1>
            <Link href="/forgot-password">Qayta so‘rash →</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-login-shell">
      <div className="auth-left">
        <div className="auth-top">
          <Link href="/">← Bosh sahifa</Link>
        </div>
        <div className="auth-body">
          <div className="auth-eyebrow">YANGI PAROL</div>
          <h1 className="auth-title">
            <em>Yangi parol</em> o‘rnating
          </h1>

          {status === 'ok' ? (
            <div className="card" style={{ padding: 16 }}>
              <div>{msg}</div>
              <div style={{ marginTop: 12 }}>
                <Link href="/sign-in">Kirish →</Link>
              </div>
            </div>
          ) : (
            <form className="auth-form" onSubmit={submit}>
              <div className="field">
                <label htmlFor="password">YANGI PAROL</label>
                <div className="field-wrap">
                  <input
                    id="password"
                    type="password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
              </div>
              <div className="field">
                <label htmlFor="confirm">PAROLNI TASDIQLANG</label>
                <div className="field-wrap">
                  <input
                    id="confirm"
                    type="password"
                    required
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                  />
                </div>
              </div>
              {status === 'err' && (
                <div style={{ color: 'var(--bad)', fontSize: 13, marginBottom: 12 }}>{msg}</div>
              )}
              <button className="auth-submit" type="submit" disabled={status === 'loading'}>
                {status === 'loading' ? 'Saqlanmoqda…' : 'Parolni yangilash'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

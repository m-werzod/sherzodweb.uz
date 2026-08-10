'use client';

/**
 * Root-level error boundary — fires when the layout itself crashes.
 * Must render its own <html><body> because the normal chrome is unavailable.
 */
import * as React from 'react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  // Same stale-Server-Action recovery as the route error boundary: a redeploy rotates action ids,
  // so a pre-deploy tab lands here — hard-reload once (guarded) to pull the fresh bundle.
  const isStaleAction = /server action|failed-to-find-server-action|was not found on the server/i.test(
    error?.message || '',
  );
  React.useEffect(() => {
    if (!isStaleAction || typeof window === 'undefined') return;
    const KEY = 'sa-reload-at';
    const last = Number(sessionStorage.getItem(KEY) || 0);
    if (Date.now() - last > 10_000) {
      sessionStorage.setItem(KEY, String(Date.now()));
      window.location.reload();
    }
  }, [isStaleAction]);

  // 100% failure visibility: browser-side crashes are reported to the log channel
  // (fire-and-forget; the server route dedupes so a hot page can't flood it).
  React.useEffect(() => {
    if (isStaleAction) return;
    try {
      void fetch('/api/client-error', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          message: error?.message || 'unknown',
          digest: error?.digest,
          url: typeof window !== 'undefined' ? window.location.href : '',
        }),
      });
    } catch {
      /* reporting must never break the error page itself */
    }
  }, [error, isStaleAction]);

  return (
    <html lang="uz">
      <body
        style={{
          margin: 0,
          minHeight: '100vh',
          display: 'grid',
          placeItems: 'center',
          background: '#1a1815',
          color: '#e8e4dc',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          padding: 24,
        }}
      >
        <div
          style={{
            maxWidth: 520,
            padding: 32,
            background: '#221f1c',
            border: '1px solid #2e2a26',
            borderRadius: 16,
          }}
        >
          <div
            style={{
              fontFamily: 'ui-monospace, monospace',
              fontSize: 11,
              letterSpacing: '0.18em',
              color: '#e89e5a',
              marginBottom: 14,
              textTransform: 'uppercase',
            }}
          >
            {isStaleAction ? 'Ilova yangilandi' : 'Server xatosi'}
          </div>
          <h1 style={{ fontSize: 36, lineHeight: 1.1, margin: '0 0 16px', fontWeight: 500 }}>
            {isStaleAction ? 'Sahifa qayta yuklanmoqda…' : 'Server biroz qoqildi.'}
          </h1>
          <p style={{ fontSize: 14, color: '#b4ada1', lineHeight: 1.6, margin: '0 0 8px' }}>
            {isStaleAction
              ? "Ilovaning yangi versiyasi chiqdi. Sahifani yangilab, qaytadan urinib ko'ring."
              : error.message || "Noma'lum xatolik yuz berdi."}
          </p>
          {!isStaleAction && error.digest && (
            <p style={{ fontFamily: 'ui-monospace, monospace', fontSize: 11, color: '#6f6960' }}>
              ID: {error.digest}
            </p>
          )}
          <div style={{ display: 'flex', gap: 10, marginTop: 18 }}>
            <button
              type="button"
              onClick={() => (isStaleAction && typeof window !== 'undefined' ? window.location.reload() : reset())}
              style={{
                padding: '10px 18px',
                background: '#a78bfa',
                color: '#1a1815',
                border: 'none',
                borderRadius: 10,
                fontSize: 14,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              {isStaleAction ? 'Yangilash' : 'Qayta urinish'}
            </button>
            {/* global-error renders OUTSIDE the app layout — Next/Link is
                unavailable here, so a plain anchor is the right tool. */}
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
            <a
              href="/"
              style={{
                padding: '10px 18px',
                color: '#e8e4dc',
                border: '1px solid #2e2a26',
                borderRadius: 10,
                fontSize: 14,
                textDecoration: 'none',
                display: 'inline-block',
              }}
            >
              Bosh sahifa
            </a>
          </div>
        </div>
      </body>
    </html>
  );
}

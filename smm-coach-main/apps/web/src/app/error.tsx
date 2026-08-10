'use client';

/**
 * Nested-route error boundary. Renders inside the existing layout chrome.
 * For root-level catastrophic failures, see global-error.tsx.
 */
import * as React from 'react';
import Link from 'next/link';

export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  // A redeploy rotates Next.js Server Action ids (they're build-hashed). A tab opened BEFORE the
  // deploy submits a form whose action id no longer exists → "Server Action … was not found". The
  // fresh bundle fixes it, so hard-reload once. Guarded by a short window so a genuinely persistent
  // failure shows the error instead of looping.
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

  return (
    <div
      style={{
        minHeight: '60vh',
        display: 'grid',
        placeItems: 'center',
        padding: 24,
      }}
    >
      <div
        className="card"
        style={{ maxWidth: 520, padding: 32 }}
      >
        <div className="eyebrow" style={{ color: 'var(--color-warm)', marginBottom: 14 }}>
          {isStaleAction ? 'ILOVA YANGILANDI' : 'KUTILMAGAN XATOLIK'}
        </div>
        <h1 className="serif" style={{ fontSize: 36, lineHeight: 1.1, margin: '0 0 16px' }}>
          {isStaleAction ? 'Sahifa qayta yuklanmoqda…' : 'Bu sahifa biroz qoqildi.'}
        </h1>
        <p
          style={{
            fontSize: 14,
            color: 'var(--color-ink-2)',
            lineHeight: 1.6,
            margin: '0 0 8px',
          }}
        >
          {isStaleAction
            ? "Ilovaning yangi versiyasi chiqdi. Sahifani yangilab, qaytadan urinib ko'ring."
            : error.message || "Noma'lum xatolik yuz berdi."}
        </p>
        {!isStaleAction && error.digest && (
          <p className="mono dim" style={{ fontSize: 11, margin: '0 0 24px' }}>
            ID: {error.digest}
          </p>
        )}
        <div className="row" style={{ marginTop: 18, gap: 10 }}>
          <button
            type="button"
            className="btn primary"
            onClick={() => (isStaleAction && typeof window !== 'undefined' ? window.location.reload() : reset())}
          >
            {isStaleAction ? 'Yangilash' : 'Qayta urinish'}
          </button>
          <Link href="/" className="btn">
            Bosh sahifa
          </Link>
        </div>
      </div>
    </div>
  );
}

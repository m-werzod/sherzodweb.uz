// Instant skeleton while the server component fetches competitor media via the
// Graph API business_discovery fan-out (~6-10s). Next.js streams this via the
// route Suspense boundary so the page never shows a blank screen.
export default function ViraleLoading() {
  return (
    <div className="fade-in">
      <div className="topbar">
        <div>
          <div className="eyebrow">VIRALE</div>
          <h1 className="page-title">
            <em>Viral</em> kontent.
          </h1>
          <div className="muted" style={{ fontSize: 14, marginTop: 8 }}>
            Raqobatchi kontenti yuklanmoqda…
          </div>
        </div>
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
          gap: 18,
        }}
      >
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="card" style={{ padding: 14, background: 'var(--color-bg-elev)' }}>
            <div
              className="shot-placeholder"
              style={{
                aspectRatio: '9 / 16',
                borderRadius: 6,
                background: 'var(--color-surface-2)',
                animation: 'pulse 1.4s ease-in-out infinite',
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

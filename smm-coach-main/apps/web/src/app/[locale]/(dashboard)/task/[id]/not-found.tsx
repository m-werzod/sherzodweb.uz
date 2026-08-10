/**
 * Scoped 404 for missing or cross-tenant task ids. Falls in here when
 * `getTaskBrief()` returns null (deleted, wrong tenant, bad id).
 */
import { Link } from '@/i18n/routing';

export default function TaskNotFound() {
  return (
    <div className="fade-in" style={{ padding: 24 }}>
      <div className="topbar">
        <div>
          <div className="eyebrow">TOPSHIRIQ TOPILMADI</div>
          <h1 className="page-title">
            Bu topshiriq <em>yo'q</em>.
          </h1>
          <div className="muted" style={{ fontSize: 14, maxWidth: 580, marginTop: 8 }}>
            Topshiriq olib tashlangan bo'lishi mumkin yoki manzil noto'g'ri.
            Ro'yxatdan boshqasini tanlang yoki yangi topshiriq yarating.
          </div>
        </div>
        <div className="topbar-right">
          <Link href="/roadmap" className="btn">
            ← Yo'l xaritasi
          </Link>
          <Link href="/dashboard" className="btn primary">
            Dashboard'ga qaytish
          </Link>
        </div>
      </div>
    </div>
  );
}

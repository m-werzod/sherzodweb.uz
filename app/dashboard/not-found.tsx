import Link from 'next/link'

export default function DashboardNotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="text-center max-w-sm">
        <div className="text-6xl font-black text-[#1e1e2e] mb-4">404</div>
        <h2 className="text-xl font-bold text-white mb-2">Page not found</h2>
        <p className="text-sm text-slate-500 mb-6">This page doesn't exist in the dashboard.</p>
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-400 border border-indigo-500/30 rounded-xl text-sm font-medium transition-colors"
        >
          Back to Overview
        </Link>
      </div>
    </div>
  )
}

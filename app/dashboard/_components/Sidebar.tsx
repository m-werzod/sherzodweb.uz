'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useSettings } from '../_lib/store'

const NAV = [
  {
    href: '/dashboard',
    label: 'Overview',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="w-5 h-5">
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </svg>
    ),
  },
  {
    href: '/dashboard/transactions',
    label: 'Transactions',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="w-5 h-5">
        <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
        <rect x="9" y="3" width="6" height="4" rx="1" />
        <path d="M9 12h6M9 16h4" />
      </svg>
    ),
  },
  {
    href: '/dashboard/analytics',
    label: 'Analytics',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="w-5 h-5">
        <path d="M3 3v18h18" />
        <path d="M7 16l4-4 4 4 4-8" />
      </svg>
    ),
  },
  {
    href: '/dashboard/categories',
    label: 'Categories',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="w-5 h-5">
        <path d="M4 6h16M4 12h10M4 18h7" />
        <circle cx="19" cy="18" r="2" />
        <path d="M19 14v2" />
      </svg>
    ),
  },
  {
    href: '/dashboard/insights',
    label: 'Smart Insights',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="w-5 h-5">
        <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    ),
    badge: 'NEW',
  },
]

export default function Sidebar() {
  const pathname = usePathname()
  const settings = useSettings()

  const syncAgo = settings.lastSync
    ? (() => {
        const ms = Date.now() - new Date(settings.lastSync!).getTime()
        const m = Math.floor(ms / 60000)
        if (m < 1) return 'just now'
        if (m < 60) return `${m}m ago`
        return `${Math.floor(m / 60)}h ago`
      })()
    : null

  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-[#0e0e18] border-r border-[#1e1e2e] flex flex-col z-40">
      {/* Brand */}
      <div className="px-5 py-5 border-b border-[#1e1e2e]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <svg viewBox="0 0 24 24" fill="white" className="w-4 h-4">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1.41 16.09V20h-2.67v-1.93c-1.71-.36-3.16-1.46-3.27-3.4h1.96c.1 1.05.82 1.87 2.65 1.87 1.96 0 2.4-.98 2.4-1.59 0-.83-.44-1.61-2.67-2.14-2.48-.6-4.18-1.62-4.18-3.67 0-1.72 1.39-2.84 3.11-3.21V4h2.67v1.95c1.86.45 2.79 1.86 2.85 3.39H14.3c-.05-1.11-.64-1.87-2.22-1.87-1.5 0-2.4.68-2.4 1.64 0 .84.65 1.39 2.67 1.91s4.18 1.39 4.18 3.91c-.01 1.83-1.38 2.83-3.12 3.16z"/>
            </svg>
          </div>
          <div>
            <div className="text-sm font-semibold text-white">FinTrack</div>
            <div className="text-[10px] text-slate-500">Business Dashboard</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="text-[10px] uppercase tracking-widest text-slate-600 px-2 mb-3 font-medium">Menu</div>
        {NAV.map(item => {
          const active = item.href === '/dashboard'
            ? pathname === '/dashboard'
            : pathname.startsWith(item.href)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group relative ${
                active
                  ? 'bg-indigo-500/15 text-indigo-400 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
              }`}
            >
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-indigo-400 rounded-r-full" />
              )}
              <span className={active ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-300 transition-colors'}>
                {item.icon}
              </span>
              <span className="flex-1">{item.label}</span>
              {item.badge && (
                <span className="text-[9px] font-bold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 px-1.5 py-0.5 rounded-full">
                  {item.badge}
                </span>
              )}
            </Link>
          )
        })}
      </nav>

      {/* Telegram Sync Status */}
      <div className="px-4 py-4 border-t border-[#1e1e2e]">
        {settings.telegramConnected ? (
          <div className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
            </span>
            <div className="flex-1 min-w-0">
              <div className="text-[11px] font-medium text-emerald-400">Telegram Synced</div>
              {syncAgo && <div className="text-[10px] text-emerald-500/70 truncate">{syncAgo}</div>}
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-slate-500/10 border border-slate-500/20">
            <span className="h-2 w-2 rounded-full bg-slate-500" />
            <div>
              <div className="text-[11px] font-medium text-slate-400">Bot not connected</div>
              <div className="text-[10px] text-slate-600">Link {settings.botUsername}</div>
            </div>
          </div>
        )}
      </div>

      {/* Back to portfolio */}
      <div className="px-4 pb-4">
        <Link
          href="/"
          className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-slate-600 hover:text-slate-400 transition-colors"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-3.5 h-3.5">
            <path d="M19 12H5M5 12l7 7M5 12l7-7" />
          </svg>
          Back to Portfolio
        </Link>
      </div>
    </aside>
  )
}

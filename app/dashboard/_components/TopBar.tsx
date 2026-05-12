'use client'

import { usePathname } from 'next/navigation'
import Link from 'next/link'
import { useDashboard } from '../_lib/store'
import { formatCurrency, getCurrentMonthKey, getTransactionsForMonth, computeMonthlyMetrics } from '../_lib/utils'
import { useMemo } from 'react'

const PAGE_LABELS: Record<string, string> = {
  '/dashboard': 'Overview',
  '/dashboard/transactions': 'Transactions',
  '/dashboard/analytics': 'Analytics',
  '/dashboard/categories': 'Categories',
  '/dashboard/insights': 'Smart Insights',
}

export default function TopBar() {
  const pathname = usePathname()
  const { state } = useDashboard()
  const currSymbol = state.settings.currencySymbol

  const currMonthTxns = useMemo(() => getTransactionsForMonth(state.transactions, getCurrentMonthKey()), [state.transactions])
  const metrics = useMemo(() => computeMonthlyMetrics(currMonthTxns), [currMonthTxns])

  const label = PAGE_LABELS[pathname] || 'Dashboard'

  return (
    <div className="sticky top-0 z-30 bg-[#090912]/80 backdrop-blur-xl border-b border-[#1e1e2e]/50">
      <div className="flex items-center justify-between px-6 py-3">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-slate-600">
          <Link href="/dashboard" className="hover:text-slate-400 transition-colors">FinTrack</Link>
          {pathname !== '/dashboard' && (
            <>
              <span>/</span>
              <span className="text-slate-400">{label}</span>
            </>
          )}
        </div>

        {/* Live summary pills */}
        <div className="hidden sm:flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-emerald-400 font-medium">+{formatCurrency(metrics.income, currSymbol)}</span>
            <span className="text-slate-700">·</span>
            <span className="text-red-400 font-medium">−{formatCurrency(metrics.expenses, currSymbol)}</span>
            <span className="text-slate-700">·</span>
            <span className={`font-semibold ${metrics.net >= 0 ? 'text-indigo-400' : 'text-red-400'}`}>
              {metrics.net >= 0 ? '+' : ''}{formatCurrency(metrics.net, currSymbol)}
            </span>
            <span className="text-slate-700 ml-1">this month</span>
          </div>

          {state.settings.telegramConnected && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/15 text-[10px] text-emerald-400">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-400" />
              </span>
              Live sync
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

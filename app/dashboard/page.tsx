'use client'

import { useState, useMemo } from 'react'
import Link from 'next/link'
import { useDashboard, useCategories } from './_lib/store'
import {
  formatCurrency, formatRelativeTime, getCurrentMonthKey, getPreviousMonthKey,
  getTransactionsForMonth, computeMonthlyMetrics, computeMetricWithChange, getDailySpending,
} from './_lib/utils'
import { simulateTelegramSync } from './_lib/mockData'
import MetricCard from './_components/MetricCard'
import QuickAdd from './_components/QuickAdd'
import AreaChart from './_components/charts/AreaChart'
import Onboarding from './_components/Onboarding'

export default function OverviewPage() {
  const { state, dispatch, isLoading } = useDashboard()
  const categories = useCategories()
  const [syncing, setSyncing] = useState(false)

  const currSymbol = state.settings.currencySymbol

  const currMonth = getCurrentMonthKey()
  const prevMonth = getPreviousMonthKey()

  const currTxns = useMemo(() => getTransactionsForMonth(state.transactions, currMonth), [state.transactions, currMonth])
  const prevTxns = useMemo(() => getTransactionsForMonth(state.transactions, prevMonth), [state.transactions, prevMonth])

  const curr = useMemo(() => computeMonthlyMetrics(currTxns), [currTxns])
  const prev = useMemo(() => computeMonthlyMetrics(prevTxns), [prevTxns])

  const incomeMetric  = useMemo(() => computeMetricWithChange(curr.income,   prev.income),   [curr, prev])
  const expenseMetric = useMemo(() => computeMetricWithChange(curr.expenses,  prev.expenses), [curr, prev])
  const netMetric     = useMemo(() => computeMetricWithChange(curr.net,       prev.net),      [curr, prev])

  const dailyData = useMemo(() => getDailySpending(state.transactions, 30), [state.transactions])

  const recent = useMemo(
    () => [...state.transactions].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()).slice(0, 8),
    [state.transactions]
  )

  const budgetCategories = useMemo(() => {
    return categories
      .filter(c => c.budget && (c.type === 'expense' || c.type === 'both'))
      .map(c => {
        const spent = currTxns.filter(t => t.type === 'expense' && t.categoryId === c.id).reduce((s, t) => s + t.amount, 0)
        return { ...c, spent, pct: Math.min((spent / c.budget!) * 100, 100) }
      })
      .sort((a, b) => b.pct - a.pct)
      .slice(0, 5)
  }, [categories, currTxns])

  function handleSync() {
    if (syncing) return
    setSyncing(true)
    setTimeout(() => {
      const newTxns = simulateTelegramSync(categories)
      dispatch({ type: 'SIMULATE_TELEGRAM_SYNC', payload: newTxns })
      setSyncing(false)
    }, 1400)
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!state.onboarded) {
    return <Onboarding />
  }

  const monthLabel = new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' })

  return (
    <div className="p-6 lg:p-8 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Overview</h1>
          <p className="text-sm text-slate-500 mt-0.5">{monthLabel}</p>
        </div>
        <button
          onClick={handleSync}
          disabled={syncing}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium border transition-all duration-200 ${
            syncing
              ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30 cursor-not-allowed'
              : 'bg-[#0e0e18] text-slate-300 border-[#1e1e2e] hover:border-indigo-500/40 hover:text-white'
          }`}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`}>
            <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {syncing ? 'Syncing…' : 'Sync Telegram'}
        </button>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <MetricCard
          label="Total Income"
          value={formatCurrency(curr.income, currSymbol)}
          change={incomeMetric.changePercent}
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5 text-emerald-400"><path d="M12 5v14M5 12l7-7 7 7" /></svg>}
          iconBg="bg-emerald-500/15"
          trend={incomeMetric.trend}
          positive={incomeMetric.trend === 'up'}
        />
        <MetricCard
          label="Total Expenses"
          value={formatCurrency(curr.expenses, currSymbol)}
          change={expenseMetric.changePercent}
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5 text-red-400"><path d="M12 19V5M5 12l7 7 7-7" /></svg>}
          iconBg="bg-red-500/15"
          trend={expenseMetric.trend}
          positive={expenseMetric.trend === 'down'}
        />
        <MetricCard
          label="Net Balance"
          value={(curr.net >= 0 ? '+' : '') + formatCurrency(curr.net, currSymbol)}
          change={netMetric.changePercent}
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5 text-indigo-400"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6" /></svg>}
          iconBg="bg-indigo-500/15"
          trend={netMetric.trend}
          positive={curr.net >= 0}
        />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Spending trend chart */}
        <div className="lg:col-span-2 bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-sm font-semibold text-white">Daily Spending — Last 30 Days</h2>
              <p className="text-xs text-slate-500 mt-0.5">Expense trend over time</p>
            </div>
            <div className="text-xs text-slate-500">
              Avg: {currSymbol}{(dailyData.reduce((s, d) => s + d.amount, 0) / Math.max(dailyData.filter(d => d.amount > 0).length, 1)).toFixed(0)}/day
            </div>
          </div>
          {dailyData.some(d => d.amount > 0) ? (
            <AreaChart data={dailyData} color="#6366f1" currencySymbol={currSymbol} height={160} />
          ) : (
            <div className="h-40 flex items-center justify-center text-sm text-slate-600">
              No expense data yet
            </div>
          )}
        </div>

        {/* Quick Add */}
        <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6">
          <h2 className="text-sm font-semibold text-white mb-4">Quick Log</h2>
          <QuickAdd />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent transactions */}
        <div className="lg:col-span-2 bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-sm font-semibold text-white">Recent Transactions</h2>
            <Link href="/dashboard/transactions" className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
              View all →
            </Link>
          </div>

          {recent.length === 0 ? (
            <div className="py-12 text-center">
              <div className="text-3xl mb-3">📭</div>
              <p className="text-sm text-slate-500">No transactions yet.</p>
              <p className="text-xs text-slate-600 mt-1">Use Quick Log above or your Telegram bot.</p>
            </div>
          ) : (
            <div className="space-y-1">
              {recent.map(tx => {
                const cat = categories.find(c => c.id === tx.categoryId)
                return (
                  <div key={tx.id} className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/3 transition-colors group">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center text-sm flex-shrink-0"
                      style={{ background: `${cat?.color || '#6b7280'}20` }}
                    >
                      {cat?.icon || '📦'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white truncate">{tx.description}</div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xs text-slate-600">{cat?.name || 'Other'}</span>
                        {tx.source === 'telegram' && (
                          <span className="text-[10px] bg-indigo-500/15 text-indigo-400 px-1.5 py-0.5 rounded-full">TG</span>
                        )}
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className={`text-sm font-semibold ${tx.type === 'income' ? 'text-emerald-400' : 'text-red-400'}`}>
                        {tx.type === 'income' ? '+' : '-'}{formatCurrency(tx.amount, currSymbol)}
                      </div>
                      <div className="text-[10px] text-slate-600">{formatRelativeTime(tx.date)}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Budget progress */}
        <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-sm font-semibold text-white">Budget Health</h2>
            <Link href="/dashboard/categories" className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
              Manage →
            </Link>
          </div>

          {budgetCategories.length === 0 ? (
            <div className="py-8 text-center">
              <div className="text-2xl mb-2">📊</div>
              <p className="text-xs text-slate-500">Set budgets in Categories to track health.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {budgetCategories.map(cat => (
                <div key={cat.id}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm">{cat.icon}</span>
                      <span className="text-xs text-slate-300 truncate max-w-[100px]">{cat.name}</span>
                    </div>
                    <div className="text-xs text-right">
                      <span className={cat.pct >= 90 ? 'text-red-400 font-medium' : cat.pct >= 70 ? 'text-amber-400' : 'text-slate-400'}>
                        {formatCurrency(cat.spent, currSymbol)}
                      </span>
                      <span className="text-slate-600"> / {formatCurrency(cat.budget!, currSymbol)}</span>
                    </div>
                  </div>
                  <div className="h-1.5 bg-[#1e1e2e] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        cat.pct >= 90 ? 'bg-red-500' : cat.pct >= 70 ? 'bg-amber-400' : 'bg-emerald-400'
                      }`}
                      style={{ width: `${cat.pct}%` }}
                    />
                  </div>
                  {cat.pct >= 90 && (
                    <div className="text-[10px] text-red-400 mt-0.5">
                      {cat.pct >= 100 ? 'Over budget!' : `${(100 - cat.pct).toFixed(0)}% remaining`}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Goals mini preview */}
          {state.goals.length > 0 && (
            <>
              <div className="mt-6 pt-5 border-t border-[#1e1e2e]">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Goals</h3>
                <div className="space-y-3">
                  {state.goals.slice(0, 2).map(g => (
                    <div key={g.id}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-slate-300">{g.icon} {g.name}</span>
                        <span className="text-xs text-slate-500">
                          {Math.round((g.currentAmount / g.targetAmount) * 100)}%
                        </span>
                      </div>
                      <div className="h-1.5 bg-[#1e1e2e] rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min((g.currentAmount / g.targetAmount) * 100, 100)}%`,
                            background: g.color,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Prev month comparison banner */}
      {prevTxns.length > 0 && (
        <div className="mt-6 bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-5">
          <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-4">Month-over-Month Comparison</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: 'Income',   curr: curr.income,   prev: prev.income,   col: 'text-emerald-400' },
              { label: 'Expenses', curr: curr.expenses, prev: prev.expenses, col: 'text-red-400' },
              { label: 'Net',      curr: curr.net,      prev: prev.net,      col: 'text-indigo-400' },
              { label: 'Transactions', curr: currTxns.length, prev: prevTxns.length, col: 'text-slate-300', noFormat: true },
            ].map(m => {
              const chg = prev.income === 0 ? 0 : ((m.curr - m.prev) / Math.abs(m.prev || 1)) * 100
              return (
                <div key={m.label}>
                  <div className="text-xs text-slate-600 mb-1">{m.label}</div>
                  <div className={`text-lg font-bold ${m.col}`}>
                    {m.noFormat ? m.curr : formatCurrency(m.curr, currSymbol)}
                  </div>
                  <div className="text-xs text-slate-600">
                    prev: {m.noFormat ? m.prev : formatCurrency(m.prev, currSymbol)}
                  </div>
                  <div className={`text-xs mt-0.5 font-medium ${chg >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                    {chg >= 0 ? '▲' : '▼'} {Math.abs(chg).toFixed(1)}%
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

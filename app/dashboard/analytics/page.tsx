'use client'

import { useMemo, useState } from 'react'
import { useDashboard, useCategories } from '../_lib/store'
import {
  formatCurrency, getLast6MonthKeys, getTransactionsForMonth, computeMonthlyMetrics,
  getMonthLabel, getCategorySpending, getDailySpending,
} from '../_lib/utils'
import BarChart from '../_components/charts/BarChart'
import DonutChart from '../_components/charts/DonutChart'
import AreaChart from '../_components/charts/AreaChart'

export default function AnalyticsPage() {
  const { state } = useDashboard()
  const categories = useCategories()
  const currSymbol = state.settings.currencySymbol
  const [activeTab, setActiveTab] = useState<'expenses' | 'income'>('expenses')

  const monthKeys = useMemo(() => getLast6MonthKeys(), [])

  const monthlyData = useMemo(() => monthKeys.map(key => {
    const txns = getTransactionsForMonth(state.transactions, key)
    const m = computeMonthlyMetrics(txns)
    return { label: getMonthLabel(key), income: m.income, expenses: m.expenses, net: m.net, key }
  }), [state.transactions, monthKeys])

  const currentMonthKey = monthKeys[monthKeys.length - 1]
  const currentMonthTxns = useMemo(() =>
    getTransactionsForMonth(state.transactions, currentMonthKey),
    [state.transactions, currentMonthKey]
  )

  const expenseBreakdown = useMemo(() =>
    getCategorySpending(currentMonthTxns, categories).map(d => ({
      label: d.category.name,
      value: d.amount,
      color: d.category.color,
      icon: d.category.icon,
    })),
    [currentMonthTxns, categories]
  )

  const incomeBreakdown = useMemo(() => {
    const total = currentMonthTxns.filter(t => t.type === 'income').reduce((s, t) => s + t.amount, 0)
    const grouped: Record<string, number> = {}
    currentMonthTxns.filter(t => t.type === 'income').forEach(t => {
      grouped[t.categoryId] = (grouped[t.categoryId] || 0) + t.amount
    })
    return Object.entries(grouped).map(([catId, amount]) => {
      const cat = categories.find(c => c.id === catId)
      return {
        label: cat?.name || 'Other',
        value: amount,
        color: cat?.color || '#6b7280',
        icon: cat?.icon || '📦',
      }
    }).sort((a, b) => b.value - a.value)
  }, [currentMonthTxns, categories])

  const dailyExpenses = useMemo(() => getDailySpending(state.transactions, 30), [state.transactions])
  const dailyIncome = useMemo(() => {
    const data: Record<string, number> = {}
    const now = new Date()
    for (let i = 29; i >= 0; i--) {
      const d = new Date(now); d.setDate(d.getDate() - i)
      data[d.toISOString().split('T')[0]] = 0
    }
    state.transactions.filter(t => t.type === 'income').forEach(t => {
      const k = t.date.split('T')[0]; if (k in data) data[k] += t.amount
    })
    return Object.entries(data).map(([date, amount]) => ({ date, amount }))
  }, [state.transactions])

  const hasData = state.transactions.length > 0

  // Best and worst months
  const bestMonth = monthlyData.reduce((a, b) => a.net > b.net ? a : b, monthlyData[0])
  const totalAllTime = {
    income: state.transactions.filter(t => t.type === 'income').reduce((s, t) => s + t.amount, 0),
    expenses: state.transactions.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0),
  }

  // Category YTD stats
  const ytdCategoryStats = useMemo(() => {
    const year = new Date().getFullYear()
    const ytdTxns = state.transactions.filter(t => t.date.startsWith(String(year)))
    return getCategorySpending(ytdTxns, categories).slice(0, 8)
  }, [state.transactions, categories])

  return (
    <div className="p-6 lg:p-8 max-w-7xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Analytics</h1>
        <p className="text-sm text-slate-500 mt-0.5">Financial performance overview</p>
      </div>

      {!hasData ? (
        <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl py-20 text-center">
          <div className="text-5xl mb-4">📊</div>
          <h3 className="text-base font-semibold text-white mb-2">Not enough data yet</h3>
          <p className="text-sm text-slate-500 max-w-xs mx-auto">
            Add at least a few transactions to see charts and breakdowns.
          </p>
        </div>
      ) : (
        <>
          {/* All-time summary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
            {[
              { label: 'All-time Income',   value: formatCurrency(totalAllTime.income,   currSymbol), color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
              { label: 'All-time Expenses', value: formatCurrency(totalAllTime.expenses, currSymbol), color: 'text-red-400',     bg: 'bg-red-500/10' },
              { label: 'All-time Net',      value: formatCurrency(totalAllTime.income - totalAllTime.expenses, currSymbol), color: 'text-indigo-400', bg: 'bg-indigo-500/10' },
              { label: 'Total Entries',     value: state.transactions.length.toString(), color: 'text-slate-300', bg: 'bg-slate-500/10' },
            ].map(s => (
              <div key={s.label} className={`${s.bg} border border-[#1e1e2e] rounded-2xl px-5 py-4`}>
                <div className="text-xs text-slate-500 mb-2">{s.label}</div>
                <div className={`text-xl font-bold ${s.color}`}>{s.value}</div>
              </div>
            ))}
          </div>

          {/* Monthly bar chart */}
          <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6 mb-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-sm font-semibold text-white">Income vs Expenses — Last 6 Months</h2>
                <p className="text-xs text-slate-500 mt-0.5">Monthly comparison</p>
              </div>
              {bestMonth && (
                <div className="text-xs text-right">
                  <span className="text-slate-600">Best month: </span>
                  <span className="text-emerald-400 font-medium">{bestMonth.label}</span>
                </div>
              )}
            </div>
            <BarChart data={monthlyData} currencySymbol={currSymbol} height={220} />
          </div>

          {/* Donut charts + net trend */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* Breakdown donut */}
            <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6">
              <div className="flex items-center gap-2 mb-5">
                <h2 className="text-sm font-semibold text-white">This Month — Breakdown</h2>
                <div className="ml-auto flex rounded-lg bg-[#090912] border border-[#1e1e2e] p-0.5 text-xs">
                  {(['expenses', 'income'] as const).map(tab => (
                    <button key={tab} onClick={() => setActiveTab(tab)}
                      className={`px-3 py-1 rounded-md font-medium capitalize transition-all ${
                        activeTab === tab ? 'bg-indigo-500/20 text-indigo-400' : 'text-slate-500 hover:text-slate-300'
                      }`}>{tab}</button>
                  ))}
                </div>
              </div>
              {(activeTab === 'expenses' ? expenseBreakdown : incomeBreakdown).length > 0 ? (
                <DonutChart
                  data={activeTab === 'expenses' ? expenseBreakdown : incomeBreakdown}
                  currencySymbol={currSymbol}
                  size={200}
                />
              ) : (
                <div className="h-40 flex items-center justify-center text-sm text-slate-600">
                  No {activeTab} this month
                </div>
              )}
            </div>

            {/* Net trend */}
            <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6">
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h2 className="text-sm font-semibold text-white">Net Profit by Month</h2>
                  <p className="text-xs text-slate-500 mt-0.5">Income minus expenses</p>
                </div>
              </div>
              <div className="space-y-3">
                {monthlyData.map(m => {
                  const maxNet = Math.max(...monthlyData.map(d => Math.abs(d.net)), 1)
                  const pct = (Math.abs(m.net) / maxNet) * 100
                  return (
                    <div key={m.key} className="flex items-center gap-3">
                      <div className="text-xs text-slate-500 w-12 flex-shrink-0">{m.label}</div>
                      <div className="flex-1 h-6 bg-[#090912] rounded-lg overflow-hidden relative">
                        <div
                          className={`h-full rounded-lg transition-all duration-500 ${m.net >= 0 ? 'bg-emerald-500/70' : 'bg-red-500/70'}`}
                          style={{ width: `${pct}%` }}
                        />
                        <div className={`absolute inset-0 flex items-center px-2 text-[10px] font-medium ${m.net >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>
                          {m.net >= 0 ? '+' : ''}{formatCurrency(m.net, currSymbol)}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Daily trends */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6">
              <h2 className="text-sm font-semibold text-white mb-1">Daily Expenses — 30 Days</h2>
              <p className="text-xs text-slate-500 mb-5">
                Total: {formatCurrency(dailyExpenses.reduce((s, d) => s + d.amount, 0), currSymbol)}
              </p>
              <AreaChart data={dailyExpenses} color="#ef4444" currencySymbol={currSymbol} height={140} />
            </div>
            <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6">
              <h2 className="text-sm font-semibold text-white mb-1">Daily Income — 30 Days</h2>
              <p className="text-xs text-slate-500 mb-5">
                Total: {formatCurrency(dailyIncome.reduce((s, d) => s + d.amount, 0), currSymbol)}
              </p>
              <AreaChart data={dailyIncome} color="#22c55e" currencySymbol={currSymbol} height={140} />
            </div>
          </div>

          {/* YTD category breakdown table */}
          <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6">
            <h2 className="text-sm font-semibold text-white mb-5">Year-to-Date Expense Categories</h2>
            {ytdCategoryStats.length === 0 ? (
              <p className="text-sm text-slate-600 text-center py-8">No expense data this year</p>
            ) : (
              <div className="space-y-1">
                {ytdCategoryStats.map((d, i) => (
                  <div key={d.category.id} className="flex items-center gap-4 px-3 py-2.5 rounded-xl hover:bg-white/2 transition-colors">
                    <span className="text-xs text-slate-600 w-5">{i + 1}</span>
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center text-sm flex-shrink-0"
                      style={{ background: `${d.category.color}20` }}>
                      {d.category.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-slate-300">{d.category.name}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-slate-600">{d.count} txns</span>
                          <span className="text-xs font-semibold text-red-400">{formatCurrency(d.amount, currSymbol)}</span>
                          <span className="text-xs text-slate-600 w-10 text-right">{d.percent.toFixed(1)}%</span>
                        </div>
                      </div>
                      <div className="h-1 bg-[#1e1e2e] rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${d.percent}%`, background: d.category.color }} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

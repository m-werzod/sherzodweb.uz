'use client'

import { useMemo, useState } from 'react'
import { useDashboard, useCategories } from '../_lib/store'
import {
  formatCurrency, formatDate, getLast6MonthKeys, getTransactionsForMonth,
  computeMonthlyMetrics, getCurrentMonthKey, uid,
} from '../_lib/utils'
import { Goal } from '../_lib/types'

// ───── CSV Export ─────
function exportCSV(transactions: ReturnType<typeof useDashboard>['state']['transactions'], categories: ReturnType<typeof useCategories>) {
  const header = ['Date', 'Type', 'Category', 'Description', 'Amount', 'Source']
  const rows = transactions.map(t => {
    const cat = categories.find(c => c.id === t.categoryId)
    return [
      new Date(t.date).toLocaleDateString(),
      t.type,
      cat?.name || 'Other',
      `"${t.description.replace(/"/g, '""')}"`,
      t.amount.toFixed(2),
      t.source,
    ].join(',')
  })
  const csv = [header.join(','), ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `fintrack-export-${new Date().toISOString().split('T')[0]}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// ───── Goal modal ─────
function GoalModal({ goal, onSave, onClose }: {
  goal?: Goal | null
  onSave: (g: Goal) => void
  onClose: () => void
}) {
  const [name, setName] = useState(goal?.name || '')
  const [icon, setIcon] = useState(goal?.icon || '🎯')
  const [target, setTarget] = useState(goal?.targetAmount ? String(goal.targetAmount) : '')
  const [current, setCurrent] = useState(goal?.currentAmount ? String(goal.currentAmount) : '0')
  const [deadline, setDeadline] = useState(goal?.deadline ? goal.deadline.split('T')[0] : '')
  const [color, setColor] = useState(goal?.color || '#6366f1')

  const ICONS = ['🎯','🛡️','🖥️','🏠','✈️','💰','📢','🏋️','📚','🚗','💊','🎓']
  const COLORS = ['#6366f1','#8b5cf6','#10b981','#f59e0b','#3b82f6','#ec4899','#14b8a6','#ef4444']

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!name || !target || !deadline) return
    onSave({
      id: goal?.id || uid(),
      name: name.trim(),
      icon,
      color,
      targetAmount: parseFloat(target),
      currentAmount: parseFloat(current) || 0,
      deadline: new Date(deadline + 'T12:00:00').toISOString(),
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6 w-full max-w-md shadow-2xl">
        <h3 className="text-sm font-semibold text-white mb-5">{goal ? 'Edit Goal' : 'New Goal'}</h3>
        <form onSubmit={submit} className="space-y-4">
          <input type="text" placeholder="Goal name" value={name} onChange={e => setName(e.target.value)}
            className="w-full bg-[#090912] border border-[#1e1e2e] rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500/50" />
          <div className="grid grid-cols-2 gap-3">
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">$</span>
              <input type="number" min="1" placeholder="Target" value={target} onChange={e => setTarget(e.target.value)}
                className="w-full bg-[#090912] border border-[#1e1e2e] rounded-xl pl-7 pr-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500/50" />
            </div>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">$</span>
              <input type="number" min="0" placeholder="Current" value={current} onChange={e => setCurrent(e.target.value)}
                className="w-full bg-[#090912] border border-[#1e1e2e] rounded-xl pl-7 pr-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500/50" />
            </div>
          </div>
          <input type="date" value={deadline} onChange={e => setDeadline(e.target.value)}
            className="w-full bg-[#090912] border border-[#1e1e2e] rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500/50" />
          <div className="flex flex-wrap gap-2">
            {ICONS.map(ic => (
              <button key={ic} type="button" onClick={() => setIcon(ic)}
                className={`w-8 h-8 rounded-lg text-lg flex items-center justify-center transition-all ${icon === ic ? 'bg-indigo-500/25 ring-1 ring-indigo-500/50' : 'hover:bg-white/5'}`}>
                {ic}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {COLORS.map(c => (
              <button key={c} type="button" onClick={() => setColor(c)}
                className={`w-7 h-7 rounded-lg transition-all ${color === c ? 'ring-2 ring-white/40 scale-110' : 'hover:scale-105'}`}
                style={{ background: c }} />
            ))}
          </div>
          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-xl text-sm text-slate-400 border border-[#1e1e2e]">Cancel</button>
            <button type="submit" className="flex-1 py-2.5 rounded-xl text-sm font-semibold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 hover:bg-indigo-500/30 transition-colors">
              {goal ? 'Save' : 'Create Goal'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ───── Main page ─────
export default function InsightsPage() {
  const { state, dispatch } = useDashboard()
  const categories = useCategories()
  const currSymbol = state.settings.currencySymbol

  const [goalModal, setGoalModal] = useState(false)
  const [editGoal, setEditGoal] = useState<Goal | null>(null)
  const [deleteGoalId, setDeleteGoalId] = useState<string | null>(null)

  // ─── Compute insights ───
  const monthKeys = useMemo(() => getLast6MonthKeys(), [])
  const monthlyData = useMemo(() => monthKeys.map(key => {
    const txns = getTransactionsForMonth(state.transactions, key)
    return { key, ...computeMonthlyMetrics(txns) }
  }), [state.transactions, monthKeys])

  const currMonthKey = getCurrentMonthKey()
  const currTxns = useMemo(() => getTransactionsForMonth(state.transactions, currMonthKey), [state.transactions, currMonthKey])
  const curr = useMemo(() => computeMonthlyMetrics(currTxns), [currTxns])

  // Forecast next month based on avg of last 3 months
  const forecast = useMemo(() => {
    const last3 = monthlyData.slice(-4, -1)
    if (last3.length === 0) return null
    const avgIncome   = last3.reduce((s, m) => s + m.income,   0) / last3.length
    const avgExpenses = last3.reduce((s, m) => s + m.expenses, 0) / last3.length
    const trend = monthlyData.length >= 2
      ? (monthlyData[monthlyData.length - 2].net - monthlyData[monthlyData.length - 3]?.net || 0) / Math.max(Math.abs(monthlyData[monthlyData.length - 3]?.net || 1), 1) * 100
      : 0
    return { income: avgIncome, expenses: avgExpenses, net: avgIncome - avgExpenses, trend }
  }, [monthlyData])

  // Anomalies: transactions > 2x avg for that category this month
  const anomalies = useMemo(() => {
    const prev3Txns = monthKeys.slice(0, 3).flatMap(k => getTransactionsForMonth(state.transactions, k))
    return currTxns.filter(t => {
      if (t.type !== 'expense') return false
      const catPrevTxns = prev3Txns.filter(p => p.categoryId === t.categoryId && p.type === 'expense')
      if (catPrevTxns.length < 2) return false
      const avg = catPrevTxns.reduce((s, p) => s + p.amount, 0) / catPrevTxns.length
      return t.amount > avg * 2.2 && t.amount > 100
    }).slice(0, 5)
  }, [currTxns, state.transactions, monthKeys])

  // Spending velocity (daily rate this month vs avg)
  const spendingVelocity = useMemo(() => {
    const dayOfMonth = new Date().getDate()
    const dailyRate = dayOfMonth > 0 ? curr.expenses / dayOfMonth : 0
    const daysInMonth = new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0).getDate()
    const projectedMonthly = dailyRate * daysInMonth
    return { dailyRate, projectedMonthly }
  }, [curr.expenses])

  // Top saving opportunities: categories with >80% budget used
  const savingOpps = useMemo(() =>
    categories
      .filter(c => c.budget && (c.type === 'expense' || c.type === 'both'))
      .map(c => {
        const spent = currTxns.filter(t => t.categoryId === c.id && t.type === 'expense').reduce((s, t) => s + t.amount, 0)
        return { ...c, spent, pct: (spent / c.budget!) * 100 }
      })
      .filter(c => c.pct >= 70)
      .sort((a, b) => b.pct - a.pct),
    [categories, currTxns]
  )

  // Best spending month
  const bestMonth = useMemo(() =>
    monthlyData.reduce((best, m) => m.net > (best?.net || -Infinity) ? m : best, monthlyData[0]),
    [monthlyData]
  )

  return (
    <div className="p-6 lg:p-8 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-white">Smart Insights</h1>
            <span className="text-[10px] font-bold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 px-2 py-0.5 rounded-full">BONUS</span>
          </div>
          <p className="text-sm text-slate-500">AI-powered analysis of your finances</p>
        </div>
        <button
          onClick={() => exportCSV(state.transactions, categories)}
          className="flex items-center gap-2 px-4 py-2.5 bg-[#0e0e18] hover:bg-[#1a1a2e] text-slate-300 border border-[#1e1e2e] hover:border-[#2d2d3d] rounded-xl text-sm font-medium transition-colors"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4">
            <path d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Export CSV
        </button>
      </div>

      {state.transactions.length < 5 ? (
        <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl py-20 text-center">
          <div className="text-5xl mb-4">🧠</div>
          <h3 className="text-base font-semibold text-white mb-2">Not enough data for insights</h3>
          <p className="text-sm text-slate-500 max-w-xs mx-auto">Add more transactions to unlock AI-powered spending insights, forecasts, and anomaly detection.</p>
        </div>
      ) : (
        <>
          {/* Key insights row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            {/* Daily burn rate */}
            <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-lg bg-orange-500/15 flex items-center justify-center">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4 text-orange-400">
                    <path d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <span className="text-xs font-medium text-slate-400">Daily Burn Rate</span>
              </div>
              <div className="text-2xl font-bold text-white">{formatCurrency(spendingVelocity.dailyRate, currSymbol)}</div>
              <div className="text-xs text-slate-500 mt-1">Projected month-end: <span className={spendingVelocity.projectedMonthly > (forecast?.expenses || 0) * 1.2 ? 'text-red-400 font-medium' : 'text-slate-300'}>{formatCurrency(spendingVelocity.projectedMonthly, currSymbol)}</span></div>
            </div>

            {/* Savings rate */}
            <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4 text-emerald-400">
                    <path d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <span className="text-xs font-medium text-slate-400">Savings Rate</span>
              </div>
              <div className={`text-2xl font-bold ${curr.income > 0 && curr.net > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {curr.income > 0 ? `${Math.max(0, ((curr.income - curr.expenses) / curr.income * 100)).toFixed(1)}%` : 'N/A'}
              </div>
              <div className="text-xs text-slate-500 mt-1">
                {curr.income > 0 ? `${formatCurrency(Math.max(curr.net, 0), currSymbol)} saved this month` : 'No income recorded'}
              </div>
            </div>

            {/* Forecast */}
            {forecast && (
              <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-8 h-8 rounded-lg bg-violet-500/15 flex items-center justify-center">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4 text-violet-400">
                      <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  </div>
                  <span className="text-xs font-medium text-slate-400">Next Month Forecast</span>
                </div>
                <div className={`text-2xl font-bold ${forecast.net >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {forecast.net >= 0 ? '+' : ''}{formatCurrency(forecast.net, currSymbol)}
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  {formatCurrency(forecast.income, currSymbol)} in · {formatCurrency(forecast.expenses, currSymbol)} out
                </div>
              </div>
            )}
          </div>

          {/* Anomalies */}
          {anomalies.length > 0 && (
            <div className="bg-[#0e0e18] border border-amber-500/20 rounded-2xl p-5 mb-6">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-lg bg-amber-500/15 flex items-center justify-center">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4 text-amber-400">
                    <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <h3 className="text-sm font-semibold text-amber-400">Spending Anomalies Detected</h3>
                <span className="text-xs bg-amber-500/15 text-amber-400 px-2 py-0.5 rounded-full">{anomalies.length}</span>
              </div>
              <div className="space-y-2">
                {anomalies.map(tx => {
                  const cat = categories.find(c => c.id === tx.categoryId)
                  return (
                    <div key={tx.id} className="flex items-center gap-3 px-3 py-2.5 bg-amber-500/5 rounded-xl border border-amber-500/10">
                      <span className="text-base">{cat?.icon || '📦'}</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-white truncate">{tx.description}</div>
                        <div className="text-xs text-slate-500">{cat?.name} · {formatDate(tx.date)}</div>
                      </div>
                      <div className="text-sm font-semibold text-amber-400">{formatCurrency(tx.amount, currSymbol)}</div>
                      <span className="text-[10px] bg-amber-500/15 text-amber-400 px-1.5 py-0.5 rounded-full">Unusual</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Saving opportunities */}
          {savingOpps.length > 0 && (
            <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-5 mb-6">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-lg bg-indigo-500/15 flex items-center justify-center">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4 text-indigo-400">
                    <path d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <h3 className="text-sm font-semibold text-white">Budget Alerts</h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {savingOpps.map(cat => (
                  <div key={cat.id} className="flex items-center gap-3 p-3 bg-[#090912] rounded-xl border border-[#1e1e2e]">
                    <span className="text-xl">{cat.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between mb-1">
                        <span className="text-xs text-slate-300">{cat.name}</span>
                        <span className={`text-xs font-semibold ${cat.pct >= 100 ? 'text-red-400' : 'text-amber-400'}`}>{cat.pct.toFixed(0)}%</span>
                      </div>
                      <div className="h-1.5 bg-[#1e1e2e] rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${cat.pct >= 100 ? 'bg-red-500' : 'bg-amber-400'}`} style={{ width: `${Math.min(cat.pct, 100)}%` }} />
                      </div>
                      <div className="text-[10px] text-slate-600 mt-1">
                        {cat.pct >= 100 ? `Over by ${formatCurrency(cat.spent - cat.budget!, currSymbol)}` : `${formatCurrency(cat.budget! - cat.spent, currSymbol)} left`}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Goals + Recurring side by side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* Goals */}
            <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-white">Financial Goals</h3>
                <button onClick={() => { setEditGoal(null); setGoalModal(true) }}
                  className="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className="w-3.5 h-3.5"><path d="M12 5v14M5 12h14" /></svg>
                  Add Goal
                </button>
              </div>
              {state.goals.length === 0 ? (
                <div className="py-8 text-center">
                  <div className="text-3xl mb-2">🎯</div>
                  <p className="text-xs text-slate-500">Set financial goals to track your progress.</p>
                  <button onClick={() => { setEditGoal(null); setGoalModal(true) }}
                    className="mt-3 text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
                    + Create first goal
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  {state.goals.map(g => {
                    const pct = Math.min((g.currentAmount / g.targetAmount) * 100, 100)
                    const daysLeft = Math.ceil((new Date(g.deadline).getTime() - Date.now()) / 86400000)
                    const needed = Math.max(g.targetAmount - g.currentAmount, 0)
                    return (
                      <div key={g.id} className="group">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-lg">{g.icon}</span>
                            <div>
                              <div className="text-sm text-white font-medium">{g.name}</div>
                              <div className="text-[10px] text-slate-600">
                                {daysLeft > 0 ? `${daysLeft}d left` : 'Deadline passed'} · Need {formatCurrency(needed, currSymbol)}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button onClick={() => { setEditGoal(g); setGoalModal(true) }}
                              className="w-6 h-6 rounded-lg bg-indigo-500/15 hover:bg-indigo-500/30 text-indigo-400 flex items-center justify-center transition-colors">
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-3 h-3">
                                <path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                              </svg>
                            </button>
                            <button onClick={() => setDeleteGoalId(g.id)}
                              className="w-6 h-6 rounded-lg bg-red-500/15 hover:bg-red-500/30 text-red-400 flex items-center justify-center transition-colors">
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-3 h-3">
                                <path d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </div>
                        </div>
                        <div className="flex justify-between text-[10px] text-slate-600 mb-1">
                          <span>{formatCurrency(g.currentAmount, currSymbol)} saved</span>
                          <span>{pct.toFixed(0)}% of {formatCurrency(g.targetAmount, currSymbol)}</span>
                        </div>
                        <div className="h-2 bg-[#1e1e2e] rounded-full overflow-hidden">
                          <div className="h-full rounded-full transition-all duration-700"
                            style={{ width: `${pct}%`, background: g.color }} />
                        </div>
                        {pct >= 100 && (
                          <div className="text-[10px] text-emerald-400 mt-1 font-medium">Goal reached!</div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Recurring transactions */}
            <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-5">
              <h3 className="text-sm font-semibold text-white mb-4">Upcoming Recurring</h3>
              {state.recurring.length === 0 ? (
                <div className="py-8 text-center">
                  <div className="text-3xl mb-2">🔄</div>
                  <p className="text-xs text-slate-500">No recurring transactions configured.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {state.recurring.filter(r => r.active).map(r => {
                    const cat = categories.find(c => c.id === r.categoryId)
                    const daysUntil = Math.ceil((new Date(r.nextDate).getTime() - Date.now()) / 86400000)
                    return (
                      <div key={r.id} className="flex items-center gap-3 p-3 bg-[#090912] rounded-xl border border-[#1e1e2e]">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm flex-shrink-0"
                          style={{ background: `${cat?.color || '#6b7280'}20` }}>
                          {cat?.icon || '🔄'}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm text-white truncate">{r.description}</div>
                          <div className="text-[10px] text-slate-600 capitalize">{r.frequency} · {cat?.name}</div>
                        </div>
                        <div className="text-right">
                          <div className={`text-sm font-semibold ${r.type === 'income' ? 'text-emerald-400' : 'text-red-400'}`}>
                            {r.type === 'income' ? '+' : '-'}{formatCurrency(r.amount, currSymbol)}
                          </div>
                          <div className={`text-[10px] ${daysUntil <= 3 ? 'text-amber-400' : 'text-slate-600'}`}>
                            {daysUntil <= 0 ? 'Due today' : `in ${daysUntil}d`}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                  <div className="pt-2 border-t border-[#1e1e2e]">
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-600">Upcoming outflows</span>
                      <span className="text-red-400 font-medium">
                        -{formatCurrency(state.recurring.filter(r => r.active && r.type === 'expense').reduce((s, r) => s + r.amount, 0), currSymbol)}/mo
                      </span>
                    </div>
                    <div className="flex justify-between text-xs mt-1">
                      <span className="text-slate-600">Upcoming inflows</span>
                      <span className="text-emerald-400 font-medium">
                        +{formatCurrency(state.recurring.filter(r => r.active && r.type === 'income').reduce((s, r) => s + r.amount, 0), currSymbol)}/mo
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Intelligent recommendations */}
          <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-violet-500/15 flex items-center justify-center">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4 text-violet-400">
                  <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <h3 className="text-sm font-semibold text-white">Recommendations</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {[
                ...(curr.expenses > curr.income * 0.9 && curr.income > 0 ? [{
                  icon: '⚠️', color: 'border-red-500/20 bg-red-500/5',
                  title: 'High expense ratio',
                  text: `You're spending ${((curr.expenses / curr.income) * 100).toFixed(0)}% of income. Consider reducing variable expenses.`,
                }] : []),
                ...(savingOpps.some(c => c.pct >= 100) ? [{
                  icon: '🚨', color: 'border-red-500/20 bg-red-500/5',
                  title: 'Budget exceeded',
                  text: `${savingOpps.filter(c => c.pct >= 100).map(c => c.name).join(', ')} exceeded monthly budget.`,
                }] : []),
                ...(forecast && forecast.net > 0 ? [{
                  icon: '📈', color: 'border-emerald-500/20 bg-emerald-500/5',
                  title: 'Positive forecast',
                  text: `Based on 3-month trends, next month looks strong with a projected net of ${formatCurrency(forecast.net, currSymbol)}.`,
                }] : []),
                ...(state.goals.length === 0 ? [{
                  icon: '🎯', color: 'border-indigo-500/20 bg-indigo-500/5',
                  title: 'Set financial goals',
                  text: 'Track savings goals to stay motivated and visualize progress toward milestones.',
                }] : []),
                {
                  icon: '🔄', color: 'border-slate-500/20 bg-slate-500/5',
                  title: 'Connect Telegram bot',
                  text: state.settings.telegramConnected
                    ? `Your bot is connected (${state.settings.botUsername}). Transactions sync automatically.`
                    : `Connect ${state.settings.botUsername} to log transactions on-the-go and keep data in sync.`,
                },
              ].slice(0, 4).map((r, i) => (
                <div key={i} className={`p-4 rounded-xl border ${r.color}`}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-base">{r.icon}</span>
                    <span className="text-xs font-semibold text-slate-200">{r.title}</span>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">{r.text}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {goalModal && (
        <GoalModal
          goal={editGoal}
          onSave={g => { dispatch({ type: editGoal ? 'UPDATE_GOAL' : 'ADD_GOAL', payload: g }); setGoalModal(false); setEditGoal(null) }}
          onClose={() => { setGoalModal(false); setEditGoal(null) }}
        />
      )}

      {deleteGoalId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setDeleteGoalId(null)} />
          <div className="relative bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6 w-full max-w-sm shadow-2xl text-center">
            <p className="text-sm text-slate-300 mb-5">Delete this goal?</p>
            <div className="flex gap-2">
              <button onClick={() => setDeleteGoalId(null)} className="flex-1 py-2.5 rounded-xl text-sm text-slate-400 border border-[#1e1e2e]">Cancel</button>
              <button onClick={() => { dispatch({ type: 'DELETE_GOAL', payload: deleteGoalId }); setDeleteGoalId(null) }}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold bg-red-500/20 text-red-400 border border-red-500/30">Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

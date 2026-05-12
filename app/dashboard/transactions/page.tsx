'use client'

import { useState, useMemo, useRef } from 'react'
import { useDashboard, useCategories } from '../_lib/store'
import { formatCurrency, formatDate, uid } from '../_lib/utils'
import { Transaction } from '../_lib/types'

function EditModal({
  tx,
  categories,
  currSymbol,
  onSave,
  onClose,
}: {
  tx: Transaction
  categories: ReturnType<typeof useCategories>
  currSymbol: string
  onSave: (t: Transaction) => void
  onClose: () => void
}) {
  const [type, setType] = useState(tx.type)
  const [amount, setAmount] = useState(String(tx.amount))
  const [categoryId, setCategoryId] = useState(tx.categoryId)
  const [description, setDescription] = useState(tx.description)
  const [date, setDate] = useState(tx.date.split('T')[0])

  const filteredCats = categories.filter(c => c.type === type || c.type === 'both')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    onSave({ ...tx, type, amount: parseFloat(amount), categoryId, description, date: new Date(date + 'T12:00:00').toISOString() })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6 w-full max-w-md shadow-2xl">
        <h3 className="text-sm font-semibold text-white mb-5">Edit Transaction</h3>
        <form onSubmit={submit} className="space-y-3">
          <div className="flex rounded-xl bg-[#090912] border border-[#1e1e2e] p-1">
            {(['expense', 'income'] as const).map(t => (
              <button key={t} type="button" onClick={() => { setType(t); setCategoryId('') }}
                className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                  type === t
                    ? t === 'expense' ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                {t === 'expense' ? '- Expense' : '+ Income'}
              </button>
            ))}
          </div>
          <div className="relative">
            <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 text-sm">{currSymbol}</span>
            <input type="number" min="0.01" step="0.01" value={amount} onChange={e => setAmount(e.target.value)}
              className="w-full bg-[#090912] border border-[#1e1e2e] rounded-xl pl-8 pr-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500/50" />
          </div>
          <input type="text" value={description} onChange={e => setDescription(e.target.value)}
            placeholder="Description"
            className="w-full bg-[#090912] border border-[#1e1e2e] rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500/50" />
          <select value={categoryId} onChange={e => setCategoryId(e.target.value)}
            className="w-full bg-[#090912] border border-[#1e1e2e] rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500/50 appearance-none">
            {filteredCats.map(c => <option key={c.id} value={c.id}>{c.icon} {c.name}</option>)}
          </select>
          <input type="date" value={date} onChange={e => setDate(e.target.value)}
            className="w-full bg-[#090912] border border-[#1e1e2e] rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500/50" />
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 py-2.5 rounded-xl text-sm text-slate-400 border border-[#1e1e2e] hover:border-[#2d2d3d] transition-colors">
              Cancel
            </button>
            <button type="submit"
              className="flex-1 py-2.5 rounded-xl text-sm font-semibold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 hover:bg-indigo-500/30 transition-colors">
              Save Changes
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function TransactionsPage() {
  const { state, dispatch } = useDashboard()
  const categories = useCategories()
  const currSymbol = state.settings.currencySymbol

  // Filters
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<'all' | 'income' | 'expense'>('all')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [sortBy, setSortBy] = useState<'date' | 'amount'>('date')
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc')
  const [page, setPage] = useState(1)
  const PER_PAGE = 15

  const [editTx, setEditTx] = useState<Transaction | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [showQuickAdd, setShowQuickAdd] = useState(false)

  const filtered = useMemo(() => {
    let txns = [...state.transactions]
    if (search.trim()) {
      const q = search.toLowerCase()
      txns = txns.filter(t =>
        t.description.toLowerCase().includes(q) ||
        categories.find(c => c.id === t.categoryId)?.name.toLowerCase().includes(q)
      )
    }
    if (typeFilter !== 'all') txns = txns.filter(t => t.type === typeFilter)
    if (categoryFilter !== 'all') txns = txns.filter(t => t.categoryId === categoryFilter)
    if (dateFrom) txns = txns.filter(t => t.date >= dateFrom)
    if (dateTo) txns = txns.filter(t => t.date <= dateTo + 'T23:59:59')
    txns.sort((a, b) => {
      const mult = sortDir === 'desc' ? -1 : 1
      if (sortBy === 'amount') return mult * (a.amount - b.amount)
      return mult * (new Date(a.date).getTime() - new Date(b.date).getTime())
    })
    return txns
  }, [state.transactions, search, typeFilter, categoryFilter, dateFrom, dateTo, sortBy, sortDir, categories])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE))
  const paginated = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE)
  const totalIncome  = filtered.filter(t => t.type === 'income').reduce((s, t)  => s + t.amount, 0)
  const totalExpense = filtered.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0)

  function toggleSort(col: 'date' | 'amount') {
    if (sortBy === col) setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    else { setSortBy(col); setSortDir('desc') }
  }

  return (
    <div className="p-6 lg:p-8 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Transactions</h1>
          <p className="text-sm text-slate-500 mt-0.5">{filtered.length} record{filtered.length !== 1 ? 's' : ''}</p>
        </div>
        <button
          onClick={() => setShowQuickAdd(v => !v)}
          className="flex items-center gap-2 px-4 py-2.5 bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-400 border border-indigo-500/30 rounded-xl text-sm font-medium transition-colors"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className="w-4 h-4">
            <path d="M12 5v14M5 12h14" />
          </svg>
          Add Transaction
        </button>
      </div>

      {/* Quick add form */}
      {showQuickAdd && (
        <div className="mb-6 bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white">New Transaction</h3>
            <button onClick={() => setShowQuickAdd(false)} className="text-slate-500 hover:text-slate-300">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4"><path d="M18 6L6 18M6 6l12 12" /></svg>
            </button>
          </div>
          <div className="max-w-md">
            <QuickAddInline categories={categories} currSymbol={currSymbol} dispatch={dispatch} onSuccess={() => setShowQuickAdd(false)} />
          </div>
        </div>
      )}

      {/* Summary bar */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-xl px-4 py-3">
          <div className="text-xs text-slate-500 mb-1">Income (filtered)</div>
          <div className="text-sm font-semibold text-emerald-400">+{formatCurrency(totalIncome, currSymbol)}</div>
        </div>
        <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-xl px-4 py-3">
          <div className="text-xs text-slate-500 mb-1">Expenses (filtered)</div>
          <div className="text-sm font-semibold text-red-400">-{formatCurrency(totalExpense, currSymbol)}</div>
        </div>
        <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-xl px-4 py-3">
          <div className="text-xs text-slate-500 mb-1">Net (filtered)</div>
          <div className={`text-sm font-semibold ${totalIncome - totalExpense >= 0 ? 'text-indigo-400' : 'text-red-400'}`}>
            {totalIncome - totalExpense >= 0 ? '+' : ''}{formatCurrency(totalIncome - totalExpense, currSymbol)}
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-4 mb-5">
        <div className="flex flex-wrap gap-3">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600">
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text" placeholder="Search transactions…" value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }}
              className="w-full bg-[#090912] border border-[#1e1e2e] rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder:text-slate-700 focus:outline-none focus:border-indigo-500/50"
            />
          </div>

          {/* Type */}
          <div className="flex rounded-xl bg-[#090912] border border-[#1e1e2e] p-1 text-xs">
            {(['all', 'income', 'expense'] as const).map(t => (
              <button key={t} onClick={() => { setTypeFilter(t); setPage(1) }}
                className={`px-3 py-1.5 rounded-lg font-medium transition-all capitalize ${
                  typeFilter === t ? 'bg-indigo-500/20 text-indigo-400' : 'text-slate-500 hover:text-slate-300'
                }`}
              >{t}</button>
            ))}
          </div>

          {/* Category */}
          <select value={categoryFilter} onChange={e => { setCategoryFilter(e.target.value); setPage(1) }}
            className="bg-[#090912] border border-[#1e1e2e] rounded-xl px-3 py-2.5 text-sm text-slate-300 focus:outline-none focus:border-indigo-500/50 appearance-none">
            <option value="all">All Categories</option>
            {categories.map(c => <option key={c.id} value={c.id}>{c.icon} {c.name}</option>)}
          </select>

          {/* Date range */}
          <input type="date" value={dateFrom} onChange={e => { setDateFrom(e.target.value); setPage(1) }}
            className="bg-[#090912] border border-[#1e1e2e] rounded-xl px-3 py-2.5 text-sm text-slate-400 focus:outline-none focus:border-indigo-500/50" />
          <input type="date" value={dateTo} onChange={e => { setDateTo(e.target.value); setPage(1) }}
            className="bg-[#090912] border border-[#1e1e2e] rounded-xl px-3 py-2.5 text-sm text-slate-400 focus:outline-none focus:border-indigo-500/50" />

          {(search || typeFilter !== 'all' || categoryFilter !== 'all' || dateFrom || dateTo) && (
            <button onClick={() => { setSearch(''); setTypeFilter('all'); setCategoryFilter('all'); setDateFrom(''); setDateTo(''); setPage(1) }}
              className="text-xs text-slate-500 hover:text-red-400 px-3 py-2.5 transition-colors">
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-[2fr_1fr_1fr_1fr_auto] gap-4 px-5 py-3 border-b border-[#1e1e2e] text-xs text-slate-600 uppercase tracking-wider">
          <div>Transaction</div>
          <button onClick={() => toggleSort('date')} className="flex items-center gap-1 hover:text-slate-400 transition-colors">
            Date {sortBy === 'date' && (sortDir === 'desc' ? '↓' : '↑')}
          </button>
          <div>Category</div>
          <button onClick={() => toggleSort('amount')} className="flex items-center gap-1 hover:text-slate-400 transition-colors text-right justify-end">
            Amount {sortBy === 'amount' && (sortDir === 'desc' ? '↓' : '↑')}
          </button>
          <div className="w-16" />
        </div>

        {paginated.length === 0 ? (
          <div className="py-20 text-center">
            <div className="text-4xl mb-3">🔍</div>
            <p className="text-sm text-slate-400 mb-1">No transactions found</p>
            <p className="text-xs text-slate-600">Try adjusting your filters</p>
          </div>
        ) : (
          <div>
            {paginated.map((tx, idx) => {
              const cat = categories.find(c => c.id === tx.categoryId)
              return (
                <div
                  key={tx.id}
                  className={`grid grid-cols-[2fr_1fr_1fr_1fr_auto] gap-4 px-5 py-3.5 items-center hover:bg-white/2 transition-colors group ${
                    idx < paginated.length - 1 ? 'border-b border-[#131320]' : ''
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm flex-shrink-0"
                      style={{ background: `${cat?.color || '#6b7280'}20` }}>
                      {cat?.icon || '📦'}
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm text-white truncate">{tx.description}</div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        {tx.source === 'telegram' && (
                          <span className="text-[9px] bg-indigo-500/15 text-indigo-400 px-1.5 py-0.5 rounded-full font-medium">TG</span>
                        )}
                        {tx.note && <span className="text-[10px] text-slate-600 truncate">{tx.note}</span>}
                      </div>
                    </div>
                  </div>
                  <div className="text-xs text-slate-500">{formatDate(tx.date)}</div>
                  <div>
                    <span className="text-xs px-2 py-1 rounded-lg" style={{ background: `${cat?.color || '#6b7280'}18`, color: cat?.color || '#94a3b8' }}>
                      {cat?.name || 'Other'}
                    </span>
                  </div>
                  <div className={`text-sm font-semibold text-right ${tx.type === 'income' ? 'text-emerald-400' : 'text-red-400'}`}>
                    {tx.type === 'income' ? '+' : '-'}{formatCurrency(tx.amount, currSymbol)}
                  </div>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity w-16 justify-end">
                    <button onClick={() => setEditTx(tx)}
                      className="w-7 h-7 rounded-lg bg-indigo-500/15 hover:bg-indigo-500/30 text-indigo-400 flex items-center justify-center transition-colors">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-3.5 h-3.5">
                        <path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    <button onClick={() => setDeleteConfirm(tx.id)}
                      className="w-7 h-7 rounded-lg bg-red-500/15 hover:bg-red-500/30 text-red-400 flex items-center justify-center transition-colors">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-3.5 h-3.5">
                        <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-5 py-4 border-t border-[#1e1e2e] flex items-center justify-between">
            <span className="text-xs text-slate-600">
              Showing {(page - 1) * PER_PAGE + 1}–{Math.min(page * PER_PAGE, filtered.length)} of {filtered.length}
            </span>
            <div className="flex items-center gap-1">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="px-3 py-1.5 rounded-lg text-xs text-slate-400 border border-[#1e1e2e] hover:border-[#2d2d3d] disabled:opacity-40 transition-colors">
                Prev
              </button>
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                const n = page <= 3 ? i + 1 : page + i - 2
                if (n < 1 || n > totalPages) return null
                return (
                  <button key={n} onClick={() => setPage(n)}
                    className={`w-8 h-8 rounded-lg text-xs transition-colors ${n === page ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30' : 'text-slate-500 hover:text-slate-300'}`}>
                    {n}
                  </button>
                )
              })}
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                className="px-3 py-1.5 rounded-lg text-xs text-slate-400 border border-[#1e1e2e] hover:border-[#2d2d3d] disabled:opacity-40 transition-colors">
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Edit modal */}
      {editTx && (
        <EditModal
          tx={editTx}
          categories={categories}
          currSymbol={currSymbol}
          onSave={t => { dispatch({ type: 'UPDATE_TRANSACTION', payload: t }); setEditTx(null) }}
          onClose={() => setEditTx(null)}
        />
      )}

      {/* Delete confirm */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setDeleteConfirm(null)} />
          <div className="relative bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6 w-full max-w-sm shadow-2xl text-center">
            <div className="w-12 h-12 rounded-2xl bg-red-500/15 border border-red-500/25 flex items-center justify-center mx-auto mb-4">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5 text-red-400">
                <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-white mb-1">Delete Transaction</h3>
            <p className="text-xs text-slate-500 mb-5">This action cannot be undone.</p>
            <div className="flex gap-2">
              <button onClick={() => setDeleteConfirm(null)} className="flex-1 py-2.5 rounded-xl text-sm text-slate-400 border border-[#1e1e2e] hover:border-[#2d2d3d] transition-colors">
                Cancel
              </button>
              <button onClick={() => { dispatch({ type: 'DELETE_TRANSACTION', payload: deleteConfirm }); setDeleteConfirm(null) }}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 transition-colors">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Inline quick-add form for the transactions page
function QuickAddInline({
  categories,
  currSymbol,
  dispatch,
  onSuccess,
}: {
  categories: ReturnType<typeof useCategories>
  currSymbol: string
  dispatch: ReturnType<typeof useDashboard>['dispatch']
  onSuccess: () => void
}) {
  const [type, setType] = useState<'income' | 'expense'>('expense')
  const [amount, setAmount] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [description, setDescription] = useState('')
  const [date, setDate] = useState(new Date().toISOString().split('T')[0])

  const filteredCats = categories.filter(c => c.type === type || c.type === 'both')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const amt = parseFloat(amount)
    if (!amount || isNaN(amt) || amt <= 0 || !categoryId || !description.trim()) return
    dispatch({
      type: 'ADD_TRANSACTION',
      payload: { id: uid(), type, amount: amt, categoryId, description: description.trim(), date: new Date(date + 'T12:00:00').toISOString(), source: 'manual' },
    })
    onSuccess()
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap gap-2 items-end">
      <div className="flex rounded-xl bg-[#090912] border border-[#1e1e2e] p-1 text-xs">
        {(['expense', 'income'] as const).map(t => (
          <button key={t} type="button" onClick={() => { setType(t); setCategoryId('') }}
            className={`px-3 py-1.5 rounded-lg font-medium transition-all ${type === t ? t === 'expense' ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400' : 'text-slate-500'}`}>
            {t === 'expense' ? '- Expense' : '+ Income'}
          </button>
        ))}
      </div>
      <div className="relative">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">{currSymbol}</span>
        <input type="number" min="0.01" step="0.01" placeholder="Amount" value={amount} onChange={e => setAmount(e.target.value)}
          className="w-32 bg-[#090912] border border-[#1e1e2e] rounded-xl pl-7 pr-3 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500/50" />
      </div>
      <input type="text" placeholder="Description" value={description} onChange={e => setDescription(e.target.value)}
        className="flex-1 min-w-[160px] bg-[#090912] border border-[#1e1e2e] rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500/50" />
      <select value={categoryId} onChange={e => setCategoryId(e.target.value)}
        className="bg-[#090912] border border-[#1e1e2e] rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500/50 appearance-none">
        <option value="">Category</option>
        {filteredCats.map(c => <option key={c.id} value={c.id}>{c.icon} {c.name}</option>)}
      </select>
      <input type="date" value={date} onChange={e => setDate(e.target.value)}
        className="bg-[#090912] border border-[#1e1e2e] rounded-xl px-3 py-2.5 text-sm text-slate-400 focus:outline-none focus:border-indigo-500/50" />
      <button type="submit" className="px-5 py-2.5 bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-400 border border-indigo-500/30 rounded-xl text-sm font-semibold transition-colors">
        Add
      </button>
    </form>
  )
}

'use client'

import { useState, useMemo } from 'react'
import { useDashboard, useCategories } from '../_lib/store'
import { formatCurrency, getCurrentMonthKey, getTransactionsForMonth } from '../_lib/utils'
import { Category } from '../_lib/types'
import { uid } from '../_lib/utils'

const CATEGORY_ICONS = ['💼','🛍️','💻','📈','🍕','🚗','🏢','📢','⚡','🏠','📱','🏥','🎯','📦','✈️','🎓','🎉','💰','🔧','🛒']
const CATEGORY_COLORS = ['#6366f1','#8b5cf6','#06b6d4','#10b981','#f59e0b','#3b82f6','#14b8a6','#ec4899','#f97316','#64748b','#84cc16','#ef4444','#a855f7','#22d3ee','#fb923c']

function CategoryModal({
  category,
  onSave,
  onClose,
}: {
  category?: Category | null
  onSave: (c: Category) => void
  onClose: () => void
}) {
  const [name, setName] = useState(category?.name || '')
  const [icon, setIcon] = useState(category?.icon || '📦')
  const [color, setColor] = useState(category?.color || '#6366f1')
  const [type, setType] = useState<Category['type']>(category?.type || 'expense')
  const [budget, setBudget] = useState(category?.budget ? String(category.budget) : '')
  const [error, setError] = useState('')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return setError('Category name is required')
    const bgt = budget ? parseFloat(budget) : undefined
    onSave({
      id: category?.id || uid(),
      name: name.trim(),
      icon,
      color,
      type,
      budget: bgt && bgt > 0 ? bgt : undefined,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6 w-full max-w-md shadow-2xl">
        <h3 className="text-sm font-semibold text-white mb-5">
          {category ? 'Edit Category' : 'New Category'}
        </h3>
        <form onSubmit={submit} className="space-y-4">
          {/* Name */}
          <div>
            <label className="text-xs text-slate-500 mb-1.5 block">Name</label>
            <input type="text" placeholder="e.g. Marketing" value={name} onChange={e => { setName(e.target.value); setError('') }}
              className="w-full bg-[#090912] border border-[#1e1e2e] rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500/50" />
          </div>

          {/* Type */}
          <div>
            <label className="text-xs text-slate-500 mb-1.5 block">Type</label>
            <div className="flex rounded-xl bg-[#090912] border border-[#1e1e2e] p-1 text-xs">
              {(['expense', 'income', 'both'] as const).map(t => (
                <button key={t} type="button" onClick={() => setType(t)}
                  className={`flex-1 py-2 rounded-lg font-medium capitalize transition-all ${
                    type === t ? 'bg-indigo-500/20 text-indigo-400' : 'text-slate-500 hover:text-slate-300'
                  }`}>{t}</button>
              ))}
            </div>
          </div>

          {/* Icon */}
          <div>
            <label className="text-xs text-slate-500 mb-1.5 block">Icon</label>
            <div className="grid grid-cols-10 gap-1.5">
              {CATEGORY_ICONS.map(ic => (
                <button key={ic} type="button" onClick={() => setIcon(ic)}
                  className={`w-8 h-8 rounded-lg text-lg flex items-center justify-center transition-all ${
                    icon === ic ? 'bg-indigo-500/25 ring-1 ring-indigo-500/50' : 'hover:bg-white/5'
                  }`}>{ic}</button>
              ))}
            </div>
          </div>

          {/* Color */}
          <div>
            <label className="text-xs text-slate-500 mb-1.5 block">Color</label>
            <div className="flex flex-wrap gap-2">
              {CATEGORY_COLORS.map(c => (
                <button key={c} type="button" onClick={() => setColor(c)}
                  className={`w-7 h-7 rounded-lg transition-all ${color === c ? 'ring-2 ring-white/40 scale-110' : 'hover:scale-105'}`}
                  style={{ background: c }} />
              ))}
            </div>
          </div>

          {/* Budget (only for expense/both) */}
          {(type === 'expense' || type === 'both') && (
            <div>
              <label className="text-xs text-slate-500 mb-1.5 block">Monthly Budget (optional)</label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 text-sm">$</span>
                <input type="number" min="0" step="1" placeholder="0" value={budget} onChange={e => setBudget(e.target.value)}
                  className="w-full bg-[#090912] border border-[#1e1e2e] rounded-xl pl-8 pr-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500/50" />
              </div>
            </div>
          )}

          {error && <p className="text-xs text-red-400">{error}</p>}

          {/* Preview */}
          <div className="flex items-center gap-3 p-3 bg-[#090912] rounded-xl border border-[#1e1e2e]">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm" style={{ background: `${color}20` }}>
              {icon}
            </div>
            <span className="text-sm font-medium" style={{ color }}>{name || 'Category Name'}</span>
            <span className="ml-auto text-xs text-slate-600 capitalize">{type}</span>
          </div>

          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose}
              className="flex-1 py-2.5 rounded-xl text-sm text-slate-400 border border-[#1e1e2e] hover:border-[#2d2d3d] transition-colors">
              Cancel
            </button>
            <button type="submit"
              className="flex-1 py-2.5 rounded-xl text-sm font-semibold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 hover:bg-indigo-500/30 transition-colors">
              {category ? 'Save Changes' : 'Create Category'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function CategoriesPage() {
  const { state, dispatch } = useDashboard()
  const categories = useCategories()
  const currSymbol = state.settings.currencySymbol

  const [modalOpen, setModalOpen] = useState(false)
  const [editCategory, setEditCategory] = useState<Category | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [typeTab, setTypeTab] = useState<'all' | 'income' | 'expense'>('all')

  const currMonthKey = getCurrentMonthKey()
  const currTxns = useMemo(() => getTransactionsForMonth(state.transactions, currMonthKey), [state.transactions, currMonthKey])

  const categoryStats = useMemo(() => {
    return categories.map(cat => {
      const txns = currTxns.filter(t => t.categoryId === cat.id)
      const totalTxns = state.transactions.filter(t => t.categoryId === cat.id)
      const spent = txns.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0)
      const earned = txns.filter(t => t.type === 'income').reduce((s, t) => s + t.amount, 0)
      return {
        ...cat,
        spent,
        earned,
        txCount: txns.length,
        totalTxCount: totalTxns.length,
        budgetPct: cat.budget ? Math.min((spent / cat.budget) * 100, 100) : null,
      }
    })
  }, [categories, currTxns, state.transactions])

  const filtered = typeTab === 'all'
    ? categoryStats
    : categoryStats.filter(c => c.type === typeTab || c.type === 'both')

  function openCreate() { setEditCategory(null); setModalOpen(true) }
  function openEdit(cat: Category) { setEditCategory(cat); setModalOpen(true) }

  function handleSave(cat: Category) {
    if (editCategory) dispatch({ type: 'UPDATE_CATEGORY', payload: cat })
    else dispatch({ type: 'ADD_CATEGORY', payload: cat })
    setModalOpen(false)
    setEditCategory(null)
  }

  function handleDelete(id: string) {
    dispatch({ type: 'DELETE_CATEGORY', payload: id })
    setDeleteConfirm(null)
  }

  const totalBudget = filtered.reduce((s, c) => s + (c.budget || 0), 0)
  const totalSpent  = filtered.filter(c => c.type === 'expense' || c.type === 'both').reduce((s, c) => s + c.spent, 0)

  return (
    <div className="p-6 lg:p-8 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Categories</h1>
          <p className="text-sm text-slate-500 mt-0.5">{categories.length} categories configured</p>
        </div>
        <button onClick={openCreate}
          className="flex items-center gap-2 px-4 py-2.5 bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-400 border border-indigo-500/30 rounded-xl text-sm font-medium transition-colors">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className="w-4 h-4"><path d="M12 5v14M5 12h14" /></svg>
          New Category
        </button>
      </div>

      {/* Summary */}
      {totalBudget > 0 && (
        <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-5 mb-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-slate-500">Total Monthly Budget</span>
            <span className="text-xs text-slate-400">{formatCurrency(totalSpent, currSymbol)} spent of {formatCurrency(totalBudget, currSymbol)}</span>
          </div>
          <div className="h-2 bg-[#1a1a2e] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${(totalSpent/totalBudget) >= 0.9 ? 'bg-red-500' : (totalSpent/totalBudget) >= 0.7 ? 'bg-amber-400' : 'bg-indigo-500'}`}
              style={{ width: `${Math.min((totalSpent / totalBudget) * 100, 100)}%` }}
            />
          </div>
          <div className="flex justify-between mt-2 text-[10px] text-slate-600">
            <span>{Math.round((totalSpent / totalBudget) * 100)}% of total budget used</span>
            <span>{formatCurrency(Math.max(totalBudget - totalSpent, 0), currSymbol)} remaining</span>
          </div>
        </div>
      )}

      {/* Type filter */}
      <div className="flex rounded-xl bg-[#0e0e18] border border-[#1e1e2e] p-1 text-sm mb-5 w-fit">
        {(['all', 'expense', 'income'] as const).map(t => (
          <button key={t} onClick={() => setTypeTab(t)}
            className={`px-4 py-2 rounded-lg font-medium capitalize transition-all ${
              typeTab === t ? 'bg-indigo-500/20 text-indigo-400' : 'text-slate-500 hover:text-slate-300'
            }`}>{t}</button>
        ))}
      </div>

      {/* Grid */}
      {filtered.length === 0 ? (
        <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl py-20 text-center">
          <div className="text-4xl mb-3">🗂️</div>
          <h3 className="text-sm font-semibold text-white mb-2">No categories yet</h3>
          <p className="text-xs text-slate-500 mb-5">Create categories to organize your transactions.</p>
          <button onClick={openCreate} className="px-5 py-2.5 bg-indigo-500/15 text-indigo-400 border border-indigo-500/30 rounded-xl text-sm font-medium">
            Create first category
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(cat => (
            <div key={cat.id} className="group bg-[#0e0e18] border border-[#1e1e2e] hover:border-[#2d2d3d] rounded-2xl p-5 transition-colors">
              {/* Cat header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center text-lg"
                    style={{ background: `${cat.color}20` }}>
                    {cat.icon}
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-white">{cat.name}</div>
                    <div className="text-xs capitalize mt-0.5" style={{ color: cat.color }}>{cat.type}</div>
                  </div>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => openEdit(cat)}
                    className="w-7 h-7 rounded-lg bg-indigo-500/15 hover:bg-indigo-500/30 text-indigo-400 flex items-center justify-center transition-colors">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-3.5 h-3.5">
                      <path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>
                  <button onClick={() => setDeleteConfirm(cat.id)}
                    className="w-7 h-7 rounded-lg bg-red-500/15 hover:bg-red-500/30 text-red-400 flex items-center justify-center transition-colors">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-3.5 h-3.5">
                      <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-2 mb-3">
                {(cat.type === 'expense' || cat.type === 'both') && (
                  <div className="bg-[#090912] rounded-lg px-3 py-2">
                    <div className="text-[10px] text-slate-600 mb-0.5">This month</div>
                    <div className="text-xs font-semibold text-red-400">{formatCurrency(cat.spent, currSymbol)}</div>
                  </div>
                )}
                {(cat.type === 'income' || cat.type === 'both') && (
                  <div className="bg-[#090912] rounded-lg px-3 py-2">
                    <div className="text-[10px] text-slate-600 mb-0.5">Earned</div>
                    <div className="text-xs font-semibold text-emerald-400">{formatCurrency(cat.earned, currSymbol)}</div>
                  </div>
                )}
                <div className="bg-[#090912] rounded-lg px-3 py-2">
                  <div className="text-[10px] text-slate-600 mb-0.5">All transactions</div>
                  <div className="text-xs font-semibold text-slate-300">{cat.totalTxCount}</div>
                </div>
              </div>

              {/* Budget bar */}
              {cat.budget && cat.budgetPct !== null && (
                <div>
                  <div className="flex justify-between text-[10px] text-slate-600 mb-1">
                    <span>Budget: {formatCurrency(cat.budget, currSymbol)}/mo</span>
                    <span className={cat.budgetPct >= 90 ? 'text-red-400 font-medium' : cat.budgetPct >= 70 ? 'text-amber-400' : ''}>
                      {cat.budgetPct.toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-1.5 bg-[#1a1a2e] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${cat.budgetPct >= 90 ? 'bg-red-500' : cat.budgetPct >= 70 ? 'bg-amber-400' : ''}`}
                      style={{
                        width: `${cat.budgetPct}%`,
                        background: cat.budgetPct >= 90 ? '#ef4444' : cat.budgetPct >= 70 ? '#f59e0b' : cat.color,
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Add card */}
          <button onClick={openCreate}
            className="group bg-[#0e0e18] border border-[#1e1e2e] border-dashed hover:border-indigo-500/40 rounded-2xl p-5 flex flex-col items-center justify-center gap-2 transition-all min-h-[160px]">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 group-hover:bg-indigo-500/20 flex items-center justify-center transition-colors">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5 text-indigo-400">
                <path d="M12 5v14M5 12h14" />
              </svg>
            </div>
            <span className="text-xs text-slate-600 group-hover:text-slate-400 transition-colors">New Category</span>
          </button>
        </div>
      )}

      {/* Modal */}
      {modalOpen && (
        <CategoryModal
          category={editCategory}
          onSave={handleSave}
          onClose={() => { setModalOpen(false); setEditCategory(null) }}
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
            <h3 className="text-sm font-semibold text-white mb-1">Delete Category</h3>
            <p className="text-xs text-slate-500 mb-1">
              Transactions in this category will not be deleted, but they will show as "Other".
            </p>
            <p className="text-xs text-slate-600 mb-5">This action cannot be undone.</p>
            <div className="flex gap-2">
              <button onClick={() => setDeleteConfirm(null)} className="flex-1 py-2.5 rounded-xl text-sm text-slate-400 border border-[#1e1e2e] hover:border-[#2d2d3d] transition-colors">
                Cancel
              </button>
              <button onClick={() => handleDelete(deleteConfirm)} className="flex-1 py-2.5 rounded-xl text-sm font-semibold bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 transition-colors">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

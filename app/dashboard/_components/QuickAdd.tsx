'use client'

import { useState } from 'react'
import { useDashboard, useCategories } from '../_lib/store'
import { uid } from '../_lib/utils'
import { Transaction } from '../_lib/types'

interface QuickAddProps {
  onSuccess?: () => void
}

export default function QuickAdd({ onSuccess }: QuickAddProps) {
  const { dispatch } = useDashboard()
  const categories = useCategories()
  const [type, setType] = useState<'income' | 'expense'>('expense')
  const [amount, setAmount] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [description, setDescription] = useState('')
  const [date, setDate] = useState(new Date().toISOString().split('T')[0])
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const filteredCats = categories.filter(c => c.type === type || c.type === 'both')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const amt = parseFloat(amount)
    if (!amount || isNaN(amt) || amt <= 0) return setError('Enter a valid amount')
    if (!categoryId) return setError('Select a category')
    if (!description.trim()) return setError('Add a description')

    const tx: Transaction = {
      id: uid(),
      type,
      amount: amt,
      categoryId,
      description: description.trim(),
      date: new Date(date + 'T12:00:00').toISOString(),
      source: 'manual',
    }
    dispatch({ type: 'ADD_TRANSACTION', payload: tx })
    setSuccess(true)
    setAmount('')
    setDescription('')
    setCategoryId('')
    setError('')
    setTimeout(() => {
      setSuccess(false)
      onSuccess?.()
    }, 1500)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {/* Type toggle */}
      <div className="flex rounded-xl bg-[#090912] border border-[#1e1e2e] p-1">
        {(['expense', 'income'] as const).map(t => (
          <button
            key={t}
            type="button"
            onClick={() => { setType(t); setCategoryId('') }}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
              type === t
                ? t === 'expense'
                  ? 'bg-red-500/20 text-red-400 shadow-sm'
                  : 'bg-emerald-500/20 text-emerald-400 shadow-sm'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            {t === 'expense' ? '− Expense' : '+ Income'}
          </button>
        ))}
      </div>

      {/* Amount */}
      <div className="relative">
        <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 text-sm font-medium">$</span>
        <input
          type="number" min="0.01" step="0.01" placeholder="0.00"
          value={amount} onChange={e => { setAmount(e.target.value); setError('') }}
          className="w-full bg-[#090912] border border-[#1e1e2e] rounded-xl pl-8 pr-4 py-3 text-white text-sm placeholder:text-slate-700 focus:outline-none focus:border-indigo-500/50 transition-colors"
        />
      </div>

      {/* Description */}
      <input
        type="text" placeholder="Description"
        value={description} onChange={e => { setDescription(e.target.value); setError('') }}
        className="w-full bg-[#090912] border border-[#1e1e2e] rounded-xl px-4 py-3 text-white text-sm placeholder:text-slate-700 focus:outline-none focus:border-indigo-500/50 transition-colors"
      />

      {/* Category */}
      <select
        value={categoryId} onChange={e => { setCategoryId(e.target.value); setError('') }}
        className="w-full bg-[#090912] border border-[#1e1e2e] rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500/50 transition-colors appearance-none"
      >
        <option value="">Select category…</option>
        {filteredCats.map(c => <option key={c.id} value={c.id}>{c.icon} {c.name}</option>)}
      </select>

      {/* Date */}
      <input
        type="date" value={date} onChange={e => setDate(e.target.value)}
        className="w-full bg-[#090912] border border-[#1e1e2e] rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-indigo-500/50 transition-colors"
      />

      {error && <p className="text-xs text-red-400">{error}</p>}

      <button
        type="submit"
        className={`w-full py-3 rounded-xl text-sm font-semibold transition-all duration-200 ${
          success
            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
            : type === 'expense'
            ? 'bg-red-500/15 hover:bg-red-500/25 text-red-400 border border-red-500/20 hover:shadow-lg hover:shadow-red-500/10'
            : 'bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-400 border border-emerald-500/20 hover:shadow-lg hover:shadow-emerald-500/10'
        }`}
      >
        {success ? '✓ Logged successfully' : `Log ${type}`}
      </button>
    </form>
  )
}

import { Transaction, Category, MonthlyMetrics, MetricWithChange } from './types'

export function formatCurrency(amount: number, symbol = '$'): string {
  return `${symbol}${Math.abs(amount).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

export function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export function formatDateShort(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function formatRelativeTime(dateStr: string): string {
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`
  return formatDateShort(dateStr)
}

export function getMonthKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

export function getCurrentMonthKey(): string {
  return getMonthKey(new Date())
}

export function getPreviousMonthKey(): string {
  const d = new Date()
  d.setMonth(d.getMonth() - 1)
  return getMonthKey(d)
}

export function getMonthLabel(key: string): string {
  const [y, m] = key.split('-').map(Number)
  const d = new Date(y, m - 1, 1)
  return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' })
}

export function getTransactionsForMonth(transactions: Transaction[], monthKey: string): Transaction[] {
  return transactions.filter(t => t.date.startsWith(monthKey))
}

export function computeMonthlyMetrics(transactions: Transaction[]): MonthlyMetrics {
  const income = transactions.filter(t => t.type === 'income').reduce((s, t) => s + t.amount, 0)
  const expenses = transactions.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0)
  return { income, expenses, net: income - expenses }
}

export function computeMetricWithChange(current: number, previous: number): MetricWithChange {
  const changePercent = previous === 0 ? 0 : ((current - previous) / previous) * 100
  return {
    current,
    previous,
    changePercent: Math.round(changePercent * 10) / 10,
    trend: changePercent > 0.5 ? 'up' : changePercent < -0.5 ? 'down' : 'flat',
  }
}

export function getCategorySpending(
  transactions: Transaction[],
  categories: Category[]
): Array<{ category: Category; amount: number; count: number; percent: number }> {
  const total = transactions.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0)
  const grouped: Record<string, { amount: number; count: number }> = {}
  transactions.filter(t => t.type === 'expense').forEach(t => {
    if (!grouped[t.categoryId]) grouped[t.categoryId] = { amount: 0, count: 0 }
    grouped[t.categoryId].amount += t.amount
    grouped[t.categoryId].count++
  })
  return Object.entries(grouped)
    .map(([catId, data]) => ({
      category: categories.find(c => c.id === catId) || {
        id: catId, name: 'Other', icon: '📦', color: '#6b7280', type: 'expense' as const,
      },
      amount: data.amount,
      count: data.count,
      percent: total > 0 ? (data.amount / total) * 100 : 0,
    }))
    .sort((a, b) => b.amount - a.amount)
}

export function getLast6MonthKeys(): string[] {
  const keys = []
  const d = new Date()
  for (let i = 5; i >= 0; i--) {
    const dd = new Date(d.getFullYear(), d.getMonth() - i, 1)
    keys.push(getMonthKey(dd))
  }
  return keys
}

export function getDailySpending(transactions: Transaction[], days = 30): Array<{ date: string; amount: number }> {
  const result: Record<string, number> = {}
  const now = new Date()
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    const key = d.toISOString().split('T')[0]
    result[key] = 0
  }
  transactions
    .filter(t => t.type === 'expense')
    .forEach(t => {
      const key = t.date.split('T')[0]
      if (key in result) result[key] += t.amount
    })
  return Object.entries(result).map(([date, amount]) => ({ date, amount }))
}

export function uid(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

export function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n))
}

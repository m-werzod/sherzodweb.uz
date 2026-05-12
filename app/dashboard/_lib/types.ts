export type TransactionType = 'income' | 'expense'

export interface Transaction {
  id: string
  type: TransactionType
  amount: number
  categoryId: string
  description: string
  date: string
  source: 'manual' | 'telegram'
  note?: string
}

export interface Category {
  id: string
  name: string
  icon: string
  color: string
  type: TransactionType | 'both'
  budget?: number
}

export interface Goal {
  id: string
  name: string
  targetAmount: number
  currentAmount: number
  deadline: string
  color: string
  icon: string
}

export interface RecurringTransaction {
  id: string
  type: TransactionType
  amount: number
  categoryId: string
  description: string
  frequency: 'daily' | 'weekly' | 'monthly'
  nextDate: string
  active: boolean
}

export interface DashboardSettings {
  currency: string
  currencySymbol: string
  telegramConnected: boolean
  lastSync: string | null
  botUsername: string
}

export interface DashboardState {
  transactions: Transaction[]
  categories: Category[]
  goals: Goal[]
  recurring: RecurringTransaction[]
  settings: DashboardSettings
  onboarded: boolean
}

export type DashboardAction =
  | { type: 'LOAD_STATE'; payload: DashboardState }
  | { type: 'ADD_TRANSACTION'; payload: Transaction }
  | { type: 'UPDATE_TRANSACTION'; payload: Transaction }
  | { type: 'DELETE_TRANSACTION'; payload: string }
  | { type: 'ADD_CATEGORY'; payload: Category }
  | { type: 'UPDATE_CATEGORY'; payload: Category }
  | { type: 'DELETE_CATEGORY'; payload: string }
  | { type: 'ADD_GOAL'; payload: Goal }
  | { type: 'UPDATE_GOAL'; payload: Goal }
  | { type: 'DELETE_GOAL'; payload: string }
  | { type: 'COMPLETE_ONBOARDING' }
  | { type: 'LOAD_DEMO_DATA' }
  | { type: 'UPDATE_SETTINGS'; payload: Partial<DashboardSettings> }
  | { type: 'SIMULATE_TELEGRAM_SYNC'; payload: Transaction[] }

export interface MonthlyMetrics {
  income: number
  expenses: number
  net: number
}

export interface MetricWithChange {
  current: number
  previous: number
  changePercent: number
  trend: 'up' | 'down' | 'flat'
}

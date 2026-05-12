import { DashboardState, Transaction, Category, Goal, RecurringTransaction } from './types'
import { uid } from './utils'

export const DEFAULT_CATEGORIES: Category[] = [
  { id: 'cat_salary',       name: 'Salary',        icon: '💼', color: '#6366f1', type: 'income' },
  { id: 'cat_sales',        name: 'Sales',          icon: '🛍️', color: '#8b5cf6', type: 'income' },
  { id: 'cat_freelance',    name: 'Freelance',      icon: '💻', color: '#06b6d4', type: 'income' },
  { id: 'cat_investment',   name: 'Investment',     icon: '📈', color: '#10b981', type: 'income' },
  { id: 'cat_food',         name: 'Food & Dining',  icon: '🍕', color: '#f59e0b', type: 'expense', budget: 600 },
  { id: 'cat_transport',    name: 'Transport',      icon: '🚗', color: '#3b82f6', type: 'expense', budget: 250 },
  { id: 'cat_office',       name: 'Office',         icon: '🏢', color: '#14b8a6', type: 'expense', budget: 400 },
  { id: 'cat_marketing',    name: 'Marketing',      icon: '📢', color: '#ec4899', type: 'expense', budget: 500 },
  { id: 'cat_utilities',    name: 'Utilities',      icon: '⚡', color: '#f97316', type: 'expense', budget: 200 },
  { id: 'cat_rent',         name: 'Rent',           icon: '🏠', color: '#64748b', type: 'expense', budget: 1400 },
  { id: 'cat_subscriptions',name: 'Subscriptions',  icon: '📱', color: '#84cc16', type: 'expense', budget: 120 },
  { id: 'cat_health',       name: 'Health',         icon: '🏥', color: '#ef4444', type: 'expense', budget: 300 },
]

function makeDate(daysAgo: number, hour = 10, minute = 0): string {
  const d = new Date()
  d.setDate(d.getDate() - daysAgo)
  d.setHours(hour, minute, 0, 0)
  return d.toISOString()
}

function makeTx(
  type: 'income' | 'expense',
  amount: number,
  categoryId: string,
  description: string,
  daysAgo: number,
  source: 'manual' | 'telegram' = 'manual',
  note?: string,
): Transaction {
  return { id: uid(), type, amount, categoryId, description, date: makeDate(daysAgo), source, note }
}

export function generateDemoTransactions(): Transaction[] {
  return [
    // Current month
    makeTx('income',  5200, 'cat_salary',        'Monthly Salary — April',           2, 'telegram'),
    makeTx('income',  1800, 'cat_sales',          'Client Project #47',               3, 'telegram'),
    makeTx('income',   650, 'cat_freelance',      'Logo Design',                      5, 'manual'),
    makeTx('expense',  420, 'cat_food',           'Team Lunch — Client Meeting',       1, 'manual'),
    makeTx('expense',  180, 'cat_transport',      'Uber Business — Site Visit',        2, 'telegram'),
    makeTx('expense', 1400, 'cat_rent',           'Office Rent — April',              4, 'manual'),
    makeTx('expense',   89, 'cat_subscriptions',  'Figma + Notion + Slack',           5, 'manual'),
    makeTx('expense',  340, 'cat_marketing',      'Google Ads Campaign',              6, 'telegram'),
    makeTx('expense',   95, 'cat_utilities',      'Electric Bill',                    7, 'manual'),
    makeTx('income',   320, 'cat_investment',     'Dividend Payment',                 8, 'telegram'),
    makeTx('expense',  210, 'cat_health',         'Team Health Check-up',             9, 'manual'),
    makeTx('expense',  155, 'cat_office',         'Stationery & Supplies',           10, 'telegram'),
    makeTx('expense',   74, 'cat_food',           'Coffee & Snacks',                 11, 'manual'),
    makeTx('income',   900, 'cat_freelance',      'WordPress Site Build',            12, 'telegram'),
    makeTx('expense',  480, 'cat_marketing',      'Instagram Promotions',            13, 'manual'),
    makeTx('expense',   65, 'cat_transport',      'Petrol',                          14, 'telegram'),

    // Previous month
    makeTx('income',  5200, 'cat_salary',         'Monthly Salary — March',          32, 'telegram'),
    makeTx('income',  2400, 'cat_sales',           'Client Project #45 & #46',        33, 'telegram'),
    makeTx('income',   500, 'cat_freelance',      'UI Audit Report',                 34, 'manual'),
    makeTx('expense',  530, 'cat_food',           'Team Lunch + Dinner Event',        35, 'manual'),
    makeTx('expense',  200, 'cat_transport',      'Travel — Client Visits',          36, 'telegram'),
    makeTx('expense', 1400, 'cat_rent',           'Office Rent — March',             37, 'manual'),
    makeTx('expense',   89, 'cat_subscriptions',  'Figma + Notion + Slack',          38, 'manual'),
    makeTx('expense',  600, 'cat_marketing',      'Facebook + Google Ads',           39, 'telegram'),
    makeTx('expense',  110, 'cat_utilities',      'Electric & Internet',             40, 'manual'),
    makeTx('expense',  280, 'cat_office',         'Printer Cartridge + Cables',      41, 'telegram'),
    makeTx('expense',  175, 'cat_health',         'Dental Visit',                    42, 'manual'),
    makeTx('income',   420, 'cat_investment',     'ETF Dividend',                    43, 'telegram'),

    // 2 months ago
    makeTx('income',  5200, 'cat_salary',         'Monthly Salary — February',       62, 'telegram'),
    makeTx('income',  1200, 'cat_sales',           'Client Project #43',              63, 'telegram'),
    makeTx('expense',  460, 'cat_food',            'Team Meals',                      64, 'manual'),
    makeTx('expense',  130, 'cat_transport',       'Taxi & Petrol',                   65, 'telegram'),
    makeTx('expense', 1400, 'cat_rent',            'Office Rent — Feb',               66, 'manual'),
    makeTx('expense',   89, 'cat_subscriptions',  'Monthly SaaS Tools',              67, 'manual'),
    makeTx('expense',  390, 'cat_marketing',      'LinkedIn Ads',                    68, 'telegram'),
    makeTx('expense',   95, 'cat_utilities',      'Utility Bills',                   69, 'manual'),
    makeTx('expense',  220, 'cat_office',         'Office Chair',                    70, 'telegram'),
    makeTx('income',   280, 'cat_investment',     'Interest Income',                 72, 'telegram'),

    // 3 months ago
    makeTx('income',  5200, 'cat_salary',         'Monthly Salary — January',        92, 'telegram'),
    makeTx('income',  3100, 'cat_sales',           'Q1 Project Bundle',               93, 'telegram'),
    makeTx('expense',  510, 'cat_food',            'Team Events + Meals',             94, 'manual'),
    makeTx('expense',  190, 'cat_transport',       'Client Visit Transport',          95, 'telegram'),
    makeTx('expense', 1400, 'cat_rent',            'Office Rent — Jan',               96, 'manual'),
    makeTx('expense',   89, 'cat_subscriptions',  'SaaS Tools',                      97, 'manual'),
    makeTx('expense',  720, 'cat_marketing',       'Year-Start Campaign',             98, 'telegram'),
    makeTx('expense',  105, 'cat_utilities',       'Utility Bills',                   99, 'manual'),
    makeTx('expense',  450, 'cat_health',          'Annual Health Screening',        100, 'manual'),
  ]
}

export const DEMO_GOALS: Goal[] = [
  {
    id: 'goal_1',
    name: 'Emergency Fund',
    targetAmount: 15000,
    currentAmount: 9200,
    deadline: (() => { const d = new Date(); d.setMonth(d.getMonth() + 4); return d.toISOString() })(),
    color: '#6366f1',
    icon: '🛡️',
  },
  {
    id: 'goal_2',
    name: 'New Workstation',
    targetAmount: 4000,
    currentAmount: 2600,
    deadline: (() => { const d = new Date(); d.setMonth(d.getMonth() + 2); return d.toISOString() })(),
    color: '#10b981',
    icon: '🖥️',
  },
  {
    id: 'goal_3',
    name: 'Marketing Budget Q3',
    targetAmount: 5000,
    currentAmount: 1100,
    deadline: (() => { const d = new Date(); d.setMonth(d.getMonth() + 3); return d.toISOString() })(),
    color: '#f59e0b',
    icon: '📢',
  },
]

export const DEMO_RECURRING: RecurringTransaction[] = [
  {
    id: 'rec_1',
    type: 'expense',
    amount: 1400,
    categoryId: 'cat_rent',
    description: 'Office Rent',
    frequency: 'monthly',
    nextDate: (() => { const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() + 1); return d.toISOString() })(),
    active: true,
  },
  {
    id: 'rec_2',
    type: 'income',
    amount: 5200,
    categoryId: 'cat_salary',
    description: 'Monthly Salary',
    frequency: 'monthly',
    nextDate: (() => { const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() + 1); return d.toISOString() })(),
    active: true,
  },
  {
    id: 'rec_3',
    type: 'expense',
    amount: 89,
    categoryId: 'cat_subscriptions',
    description: 'SaaS Subscriptions',
    frequency: 'monthly',
    nextDate: (() => { const d = new Date(); d.setDate(5); d.setMonth(d.getMonth() + 1); return d.toISOString() })(),
    active: true,
  },
]

export const DEMO_STATE: DashboardState = {
  transactions: generateDemoTransactions(),
  categories: DEFAULT_CATEGORIES,
  goals: DEMO_GOALS,
  recurring: DEMO_RECURRING,
  settings: {
    currency: 'USD',
    currencySymbol: '$',
    telegramConnected: true,
    lastSync: new Date(Date.now() - 1000 * 60 * 8).toISOString(),
    botUsername: '@FinanceTrackerBot',
  },
  onboarded: true,
}

export const EMPTY_STATE: DashboardState = {
  transactions: [],
  categories: DEFAULT_CATEGORIES,
  goals: [],
  recurring: [],
  settings: {
    currency: 'USD',
    currencySymbol: '$',
    telegramConnected: false,
    lastSync: null,
    botUsername: '@FinanceTrackerBot',
  },
  onboarded: false,
}

// Telegram sync simulation — returns plausible new transactions
export function simulateTelegramSync(categories: Category[]): Transaction[] {
  const options = [
    { type: 'expense' as const, amount: 48,   catId: 'cat_food',      desc: 'Lunch via Telegram' },
    { type: 'expense' as const, amount: 120,  catId: 'cat_transport', desc: 'Uber — bot log' },
    { type: 'income'  as const, amount: 750,  catId: 'cat_sales',     desc: 'New order via bot' },
    { type: 'expense' as const, amount: 35,   catId: 'cat_utilities', desc: 'Internet top-up' },
    { type: 'income'  as const, amount: 1200, catId: 'cat_freelance', desc: 'Project payment — bot' },
  ]
  const count = Math.floor(Math.random() * 2) + 1
  return options.slice(0, count).map(o => ({
    id: uid(),
    type: o.type,
    amount: o.amount,
    categoryId: o.catId,
    description: o.desc,
    date: new Date().toISOString(),
    source: 'telegram' as const,
  }))
}

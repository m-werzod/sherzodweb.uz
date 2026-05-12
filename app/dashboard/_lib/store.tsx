'use client'

import React, { createContext, useContext, useReducer, useEffect, useCallback } from 'react'
import { DashboardState, DashboardAction, Transaction, Category, Goal } from './types'
import { EMPTY_STATE, DEMO_STATE } from './mockData'

const STORAGE_KEY = 'fintrack_dashboard_v1'

function reducer(state: DashboardState, action: DashboardAction): DashboardState {
  switch (action.type) {
    case 'LOAD_STATE':
      return action.payload

    case 'ADD_TRANSACTION':
      return { ...state, transactions: [action.payload, ...state.transactions] }

    case 'UPDATE_TRANSACTION':
      return {
        ...state,
        transactions: state.transactions.map(t =>
          t.id === action.payload.id ? action.payload : t
        ),
      }

    case 'DELETE_TRANSACTION':
      return { ...state, transactions: state.transactions.filter(t => t.id !== action.payload) }

    case 'ADD_CATEGORY':
      return { ...state, categories: [...state.categories, action.payload] }

    case 'UPDATE_CATEGORY':
      return {
        ...state,
        categories: state.categories.map(c => c.id === action.payload.id ? action.payload : c),
      }

    case 'DELETE_CATEGORY':
      return { ...state, categories: state.categories.filter(c => c.id !== action.payload) }

    case 'ADD_GOAL':
      return { ...state, goals: [...state.goals, action.payload] }

    case 'UPDATE_GOAL':
      return {
        ...state,
        goals: state.goals.map(g => g.id === action.payload.id ? action.payload : g),
      }

    case 'DELETE_GOAL':
      return { ...state, goals: state.goals.filter(g => g.id !== action.payload) }

    case 'COMPLETE_ONBOARDING':
      return { ...state, onboarded: true }

    case 'LOAD_DEMO_DATA':
      return { ...DEMO_STATE }

    case 'UPDATE_SETTINGS':
      return { ...state, settings: { ...state.settings, ...action.payload } }

    case 'SIMULATE_TELEGRAM_SYNC':
      return {
        ...state,
        transactions: [...action.payload, ...state.transactions],
        settings: {
          ...state.settings,
          lastSync: new Date().toISOString(),
          telegramConnected: true,
        },
      }

    default:
      return state
  }
}

interface DashboardContextType {
  state: DashboardState
  dispatch: React.Dispatch<DashboardAction>
  isLoading: boolean
}

const DashboardContext = createContext<DashboardContextType | null>(null)

export function DashboardProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, EMPTY_STATE)
  const [isLoading, setIsLoading] = React.useState(true)

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved) as DashboardState
        dispatch({ type: 'LOAD_STATE', payload: parsed })
      }
    } catch {
      // ignore parse errors
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Persist to localStorage on every state change
  useEffect(() => {
    if (!isLoading) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
      } catch {
        // ignore storage errors
      }
    }
  }, [state, isLoading])

  return (
    <DashboardContext.Provider value={{ state, dispatch, isLoading }}>
      {children}
    </DashboardContext.Provider>
  )
}

export function useDashboard() {
  const ctx = useContext(DashboardContext)
  if (!ctx) throw new Error('useDashboard must be used within DashboardProvider')
  return ctx
}

// Convenience hooks
export function useTransactions() {
  const { state } = useDashboard()
  return state.transactions
}

export function useCategories() {
  const { state } = useDashboard()
  return state.categories
}

export function useGoals() {
  const { state } = useDashboard()
  return state.goals
}

export function useSettings() {
  const { state } = useDashboard()
  return state.settings
}

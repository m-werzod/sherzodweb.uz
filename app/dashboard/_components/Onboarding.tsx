'use client'

import { useState } from 'react'
import { useDashboard } from '../_lib/store'
import QuickAdd from './QuickAdd'

export default function Onboarding() {
  const { dispatch } = useDashboard()
  const [step, setStep] = useState<'welcome' | 'add-transaction' | 'done'>('welcome')

  function loadDemo() {
    dispatch({ type: 'LOAD_DEMO_DATA' })
  }

  if (step === 'done') {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="text-center max-w-md">
          <div className="w-20 h-20 rounded-2xl bg-emerald-500/15 border border-emerald-500/25 flex items-center justify-center mx-auto mb-6 text-4xl">
            🎉
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">You're all set!</h2>
          <p className="text-slate-400 mb-6">Your first transaction has been logged. Your dashboard is ready.</p>
          <button
            onClick={() => dispatch({ type: 'COMPLETE_ONBOARDING' })}
            className="px-6 py-3 bg-indigo-500 hover:bg-indigo-400 text-white text-sm font-semibold rounded-xl transition-colors"
          >
            Open Dashboard
          </button>
        </div>
      </div>
    )
  }

  if (step === 'add-transaction') {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <button
            onClick={() => setStep('welcome')}
            className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 mb-6 transition-colors"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4">
              <path d="M19 12H5M5 12l7 7M5 12l7-7" />
            </svg>
            Back
          </button>
          <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Log your first transaction</h2>
            <p className="text-sm text-slate-400 mb-6">Add an income or expense to get started.</p>
            <QuickAdd onSuccess={() => { dispatch({ type: 'COMPLETE_ONBOARDING' }) }} />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center mx-auto mb-5 shadow-xl shadow-indigo-500/25">
            <svg viewBox="0 0 24 24" fill="white" className="w-8 h-8">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1.41 16.09V20h-2.67v-1.93c-1.71-.36-3.16-1.46-3.27-3.4h1.96c.1 1.05.82 1.87 2.65 1.87 1.96 0 2.4-.98 2.4-1.59 0-.83-.44-1.61-2.67-2.14-2.48-.6-4.18-1.62-4.18-3.67 0-1.72 1.39-2.84 3.11-3.21V4h2.67v1.95c1.86.45 2.79 1.86 2.85 3.39H14.3c-.05-1.11-.64-1.87-2.22-1.87-1.5 0-2.4.68-2.4 1.64 0 .84.65 1.39 2.67 1.91s4.18 1.39 4.18 3.91c-.01 1.83-1.38 2.83-3.12 3.16z"/>
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Welcome to FinTrack</h1>
          <p className="text-slate-400 max-w-sm mx-auto">
            Your business finance dashboard. Track income, expenses, and insights — synced with your Telegram bot.
          </p>
        </div>

        {/* Options */}
        <div className="grid grid-cols-1 gap-4 mb-6">
          <button
            onClick={() => setStep('add-transaction')}
            className="group flex items-start gap-4 p-5 bg-[#0e0e18] border border-[#1e1e2e] hover:border-indigo-500/40 rounded-2xl text-left transition-all duration-200"
          >
            <div className="w-10 h-10 rounded-xl bg-indigo-500/15 flex items-center justify-center flex-shrink-0 group-hover:bg-indigo-500/25 transition-colors">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5 text-indigo-400">
                <path d="M12 5v14M5 12h14" />
              </svg>
            </div>
            <div>
              <div className="text-sm font-semibold text-white mb-0.5">Start fresh</div>
              <div className="text-xs text-slate-500">Log your first transaction and build your data from scratch.</div>
            </div>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4 text-slate-600 group-hover:text-slate-400 ml-auto mt-1 transition-colors">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>

          <button
            onClick={loadDemo}
            className="group flex items-start gap-4 p-5 bg-[#0e0e18] border border-[#1e1e2e] hover:border-violet-500/40 rounded-2xl text-left transition-all duration-200"
          >
            <div className="w-10 h-10 rounded-xl bg-violet-500/15 flex items-center justify-center flex-shrink-0 group-hover:bg-violet-500/25 transition-colors">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5 text-violet-400">
                <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <div>
              <div className="text-sm font-semibold text-white mb-0.5">Load demo data</div>
              <div className="text-xs text-slate-500">Explore with 4 months of realistic business transactions already loaded.</div>
            </div>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4 text-slate-600 group-hover:text-slate-400 ml-auto mt-1 transition-colors">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        {/* Telegram info */}
        <div className="flex items-start gap-3 p-4 bg-[#0e0e18] border border-[#1e1e2e] rounded-xl">
          <span className="text-lg">✈️</span>
          <div>
            <div className="text-xs font-medium text-slate-300 mb-0.5">Telegram Bot Integration</div>
            <div className="text-xs text-slate-500">
              Transactions you log in Telegram automatically appear here. No setup needed — data syncs in real time.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

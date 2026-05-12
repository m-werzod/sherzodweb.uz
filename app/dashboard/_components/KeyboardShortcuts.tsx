'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

export default function KeyboardShortcuts() {
  const router = useRouter()
  const [showHelp, setShowHelp] = useState(false)

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      // Ignore when typing in inputs
      const tag = (e.target as HTMLElement).tagName.toLowerCase()
      if (['input', 'textarea', 'select'].includes(tag)) return

      // ? → show shortcut help
      if (e.key === '?') { setShowHelp(v => !v); return }

      // g + key combos for navigation
      if (e.key === 'Escape') { setShowHelp(false); return }

      if (e.altKey) {
        switch (e.key) {
          case '1': router.push('/dashboard'); break
          case '2': router.push('/dashboard/transactions'); break
          case '3': router.push('/dashboard/analytics'); break
          case '4': router.push('/dashboard/categories'); break
          case '5': router.push('/dashboard/insights'); break
        }
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [router])

  if (!showHelp) {
    return (
      <button
        onClick={() => setShowHelp(true)}
        className="fixed bottom-5 left-[268px] z-40 w-7 h-7 rounded-lg bg-[#1e1e2e] border border-[#2d2d3d] text-slate-600 hover:text-slate-400 text-xs flex items-center justify-center transition-colors"
        title="Keyboard shortcuts (?)"
      >
        ?
      </button>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setShowHelp(false)}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6 w-full max-w-sm shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-semibold text-white">Keyboard Shortcuts</h3>
          <button onClick={() => setShowHelp(false)} className="text-slate-500 hover:text-slate-300">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </div>
        <div className="space-y-1.5">
          {[
            { keys: ['Alt', '1'], label: 'Go to Overview' },
            { keys: ['Alt', '2'], label: 'Go to Transactions' },
            { keys: ['Alt', '3'], label: 'Go to Analytics' },
            { keys: ['Alt', '4'], label: 'Go to Categories' },
            { keys: ['Alt', '5'], label: 'Go to Smart Insights' },
            { keys: ['?'],        label: 'Toggle this help' },
            { keys: ['Esc'],      label: 'Close dialogs' },
          ].map(s => (
            <div key={s.label} className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-white/3">
              <span className="text-xs text-slate-400">{s.label}</span>
              <div className="flex items-center gap-1">
                {s.keys.map((k, i) => (
                  <span key={i} className="px-1.5 py-0.5 bg-[#1e1e2e] border border-[#2d2d3d] rounded text-[10px] text-slate-400 font-mono">{k}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

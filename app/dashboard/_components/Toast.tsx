'use client'

import { createContext, useContext, useState, useCallback, useEffect } from 'react'

type ToastType = 'success' | 'error' | 'info' | 'warning'

interface Toast {
  id: string
  message: string
  type: ToastType
}

interface ToastContextType {
  toast: (message: string, type?: ToastType) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const toast = useCallback((message: string, type: ToastType = 'success') => {
    const id = Math.random().toString(36).slice(2)
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => removeToast(id), 3500)
  }, [removeToast])

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/* Toast container */}
      <div className="fixed bottom-5 right-5 z-[100] flex flex-col gap-2 pointer-events-none">
        {toasts.map(t => (
          <ToastItem key={t.id} toast={t} onDismiss={() => removeToast(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true))
    const t = setTimeout(() => setVisible(false), 3000)
    return () => clearTimeout(t)
  }, [])

  const styles: Record<ToastType, { bg: string; icon: string; text: string }> = {
    success: { bg: 'bg-emerald-500/15 border-emerald-500/30', icon: '✓', text: 'text-emerald-400' },
    error:   { bg: 'bg-red-500/15 border-red-500/30',         icon: '✕', text: 'text-red-400' },
    info:    { bg: 'bg-indigo-500/15 border-indigo-500/30',   icon: 'i', text: 'text-indigo-400' },
    warning: { bg: 'bg-amber-500/15 border-amber-500/30',     icon: '!', text: 'text-amber-400' },
  }
  const s = styles[toast.type]

  return (
    <div
      onClick={onDismiss}
      className={`pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl border ${s.bg} shadow-xl backdrop-blur-md cursor-pointer transition-all duration-300 ${
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
      }`}
    >
      <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${s.text} border border-current/30`}>
        {s.icon}
      </span>
      <span className="text-sm text-slate-200 max-w-xs">{toast.message}</span>
    </div>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be inside ToastProvider')
  return ctx.toast
}

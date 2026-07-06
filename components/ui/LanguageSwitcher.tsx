'use client'
import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { localeList } from '@/lib/i18n/config'
import { useLanguage } from '@/lib/i18n/LanguageContext'

export default function LanguageSwitcher({ variant = 'desktop' }: { variant?: 'desktop' | 'mobile' | 'compact' }) {
  const { locale, setLocale } = useLanguage()
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const active = localeList.find((l) => l.code === locale)!

  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  const isMobile = variant === 'mobile'
  const isCompact = variant === 'compact'

  return (
    <div ref={rootRef} className={`relative ${isMobile ? 'w-full' : ''}`}>
      {isCompact ? (
        <button
          onClick={() => setOpen((o) => !o)}
          aria-label="Change language"
          className="w-9 h-9 rounded-xl border border-white/10 bg-white/5 hover:border-[#38bdf8]/30 hover:bg-[#38bdf8]/5 transition-all duration-200 flex items-center justify-center"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={active.flag} alt={active.label} className="w-5 h-3.5 rounded-[2px] object-cover shrink-0" />
        </button>
      ) : (
        <button
          onClick={() => setOpen((o) => !o)}
          aria-label="Change language"
          className={`flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 hover:border-[#38bdf8]/30 hover:bg-[#38bdf8]/5 transition-all duration-200 ${
            isMobile ? 'w-full px-4 py-3 justify-between' : 'px-3 py-2 text-sm'
          }`}
        >
          <span className="flex items-center gap-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={active.flag} alt={active.label} className="w-5 h-3.5 rounded-[2px] object-cover shrink-0" />
            <span className={`font-medium ${isMobile ? 'text-sm text-slate-300' : 'text-slate-300'}`}>{active.nativeLabel}</span>
          </span>
          <svg
            className={`w-3.5 h-3.5 text-slate-500 shrink-0 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
      )}

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className={`${
              isMobile ? 'relative mt-1.5 w-full' : 'absolute right-0 mt-1.5 w-40'
            } rounded-xl border border-white/10 bg-[#0a1628] shadow-2xl shadow-black/50 overflow-hidden z-50`}
          >
            {localeList.map((l) => (
              <button
                key={l.code}
                onClick={() => {
                  setLocale(l.code)
                  setOpen(false)
                }}
                className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-left transition-colors ${
                  l.code === locale ? 'bg-[#38bdf8]/10 text-[#38bdf8]' : 'text-slate-300 hover:bg-white/5 hover:text-white'
                }`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={l.flag} alt={l.label} className="w-5 h-3.5 rounded-[2px] object-cover shrink-0" />
                <span className="font-medium">{l.nativeLabel}</span>
                {l.code === locale && (
                  <svg className="w-3.5 h-3.5 ml-auto shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

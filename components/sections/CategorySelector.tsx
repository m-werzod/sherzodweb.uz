'use client'
import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import Link from 'next/link'
import { ACCENT_CLASSES, type CategoryData } from '@/lib/resumeData'
import { useLanguage } from '@/lib/i18n/LanguageContext'

const icons: Record<CategoryData['icon'], ReactNode> = {
  code: (
    <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
    </svg>
  ),
  layout: (
    <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/>
    </svg>
  ),
  sparkles: (
    <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3l1.8 5.6L19.5 10l-5.7 1.4L12 17l-1.8-5.6L4.5 10l5.7-1.4L12 3z"/>
    </svg>
  ),
  'shield-check': (
    <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/>
    </svg>
  ),
}

export default function CategorySelector() {
  const { ui, categoryList } = useLanguage()
  const pitches: Record<string, string> = {
    'full-stack': ui.categorySelector.pitchFullStack,
    frontend: ui.categorySelector.pitchFrontend,
    'ai-specialist': ui.categorySelector.pitchAiSpecialist,
    'qa-tester': ui.categorySelector.pitchQaTester,
  }

  return (
    <section className="py-20 px-6">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <p className="text-xs text-[#38bdf8] font-semibold tracking-[0.25em] uppercase mb-3">{ui.categorySelector.eyebrow}</p>
          <h2 className="text-3xl md:text-4xl font-black text-white mb-4">
            {ui.categorySelector.headingPrefix} <span className="text-[#38bdf8]">{ui.categorySelector.headingHighlight}</span>
          </h2>
          <p className="text-slate-400 max-w-xl mx-auto text-sm leading-relaxed">
            {ui.categorySelector.subtitle}
          </p>
        </motion.div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {categoryList.map((cat, i) => {
            const accent = ACCENT_CLASSES[cat.accent]
            return (
              <motion.div
                key={cat.slug}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                whileHover={{ y: -6 }}
              >
                <Link
                  href={`/${cat.slug}`}
                  className="group relative flex flex-col h-full p-6 rounded-2xl border border-white/10 bg-[#0a1628] hover:border-white/20 transition-all duration-300 hover:shadow-2xl hover:shadow-sky-950/60"
                >
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 border ${accent.border} ${accent.bg} ${accent.text}`}>
                    {icons[cat.icon]}
                  </div>
                  <h3 className="text-base font-bold text-white mb-2 group-hover:text-[#38bdf8] transition-colors">
                    {cat.label}
                  </h3>
                  <p className="text-xs text-slate-400 leading-relaxed flex-1">{pitches[cat.slug]}</p>
                  <span className={`mt-4 inline-flex items-center gap-1.5 text-xs font-semibold ${accent.text}`}>
                    {ui.categorySelector.viewPath}
                    <svg className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                    </svg>
                  </span>
                </Link>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

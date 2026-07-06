'use client'
import { motion } from 'framer-motion'
import Link from 'next/link'
import type { CategoryKey } from '@/lib/resumeData'
import { ACCENT_CLASSES } from '@/lib/resumeData'
import { useLanguage } from '@/lib/i18n/LanguageContext'
import { formatTemplate } from '@/lib/i18n/format'

export default function CategoryAbout({ category }: { category: CategoryKey }) {
  const { ui, categories } = useLanguage()
  const data = categories[category]
  const accent = ACCENT_CLASSES[data.accent]

  return (
    <div className="min-h-screen pt-36 pb-24 px-6">
      <div className="max-w-5xl mx-auto">

        {/* Summary */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-16"
        >
          <p className={`text-xs font-semibold tracking-[0.25em] uppercase mb-3 ${accent.text}`}>{data.label} {ui.categoryAbout.profileSuffix}</p>
          <h1 className="text-4xl md:text-5xl font-black text-white mb-4">{data.fullTitle}</h1>
          <p className="text-slate-400 text-base md:text-lg mb-6 font-medium">{data.tagline}</p>
          <div className="space-y-4 text-slate-400 leading-relaxed max-w-3xl">
            {data.summary.map((paragraph, i) => (
              <p key={i}>{paragraph}</p>
            ))}
          </div>
        </motion.div>

        {/* Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-20"
        >
          {data.heroStats.map((stat) => (
            <div key={stat.label} className="text-center p-6 rounded-2xl border border-white/10 bg-[#0a1628] hover:border-white/20 transition-colors">
              <p className={`text-2xl md:text-3xl font-black mb-1 ${accent.text}`}>{stat.value}</p>
              <p className="text-xs text-slate-500 font-medium leading-snug">{stat.label}</p>
            </div>
          ))}
        </motion.div>

        {/* How I Work — QA only */}
        {data.howIWork && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className={`mb-20 p-8 rounded-3xl border ${accent.border} ${accent.bg}`}
          >
            <h2 className="text-xl font-black text-white mb-5">{data.howIWork.title}</h2>
            <ul className="space-y-3">
              {data.howIWork.bullets.map((b, i) => (
                <li key={i} className="flex gap-3 text-sm text-slate-300 leading-relaxed">
                  <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${accent.dot}`} />
                  {b}
                </li>
              ))}
            </ul>
          </motion.div>
        )}

        {/* Competencies */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mb-20"
        >
          <h2 className="text-2xl font-black text-white mb-8">{ui.categoryAbout.coreCompetencies}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {data.competencies.map((group) => (
              <div key={group.category} className="p-6 rounded-2xl border border-white/10 bg-[#0a1628]">
                <h3 className={`text-sm font-bold uppercase tracking-wider mb-4 ${accent.text}`}>{group.category}</h3>
                <div className="flex flex-wrap gap-2">
                  {group.items.map((skillItem) => (
                    <span key={skillItem} className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white/5 text-slate-300 border border-white/5">
                      {skillItem}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Experience */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mb-20"
        >
          <h2 className="text-2xl font-black text-white mb-8">{ui.categoryAbout.professionalExperience}</h2>
          <div className="space-y-5">
            {data.experience.map((exp) => (
              <div key={`${exp.role}-${exp.company}`} className="p-6 rounded-2xl border border-white/10 bg-[#0a1628] hover:border-white/20 transition-colors">
                <div className="flex flex-wrap items-start justify-between gap-2 mb-4">
                  <div>
                    <h3 className="text-base font-bold text-white leading-snug">{exp.role}</h3>
                    {exp.companyHref ? (
                      <Link href={exp.companyHref} target="_blank" rel="noopener noreferrer" className={`text-sm font-medium hover:underline ${accent.text}`}>
                        {exp.company}
                      </Link>
                    ) : (
                      <p className={`text-sm font-medium ${accent.text}`}>{exp.company}</p>
                    )}
                  </div>
                  <span className="text-xs text-slate-500 font-semibold whitespace-nowrap px-2.5 py-1 rounded-full bg-white/5 border border-white/10">
                    {exp.period}
                  </span>
                </div>
                <ul className="space-y-2">
                  {exp.bullets.map((b, i) => (
                    <li key={i} className="flex gap-2.5 text-sm text-slate-400 leading-relaxed">
                      <span className={`mt-1.5 w-1 h-1 rounded-full shrink-0 ${accent.dot}`} />
                      {b}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Languages */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mb-20"
        >
          <h2 className="text-2xl font-black text-white mb-8">{ui.categoryAbout.languages}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {data.languages.map((l, i) => (
              <motion.div
                key={l.name}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="p-5 rounded-2xl border border-white/10 bg-[#0a1628] hover:border-white/20 transition-all"
              >
                <div className="flex items-center gap-3 mb-3">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={l.flag} alt={`${l.name} flag`} className="w-8 h-6 rounded object-cover shrink-0 border border-white/10" />
                  <div>
                    <p className="text-sm font-bold text-white">{l.name}</p>
                    <p className="text-xs text-slate-500">{l.level}</p>
                  </div>
                </div>
                <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    whileInView={{ width: `${l.fill}%` }}
                    viewport={{ once: true }}
                    transition={{ duration: 1, delay: i * 0.15, ease: 'easeOut' }}
                    className={`h-full rounded-full bg-gradient-to-r ${accent.from}`}
                  />
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Education & Certifications */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-20"
        >
          <div className="p-6 rounded-2xl border border-white/10 bg-[#0a1628]">
            <h2 className="text-lg font-black text-white mb-5">{ui.categoryAbout.education}</h2>
            <ul className="space-y-3">
              {data.education.map((e) => (
                <li key={e} className="flex gap-2.5 text-sm text-slate-400 leading-relaxed">
                  <span className={`mt-1.5 w-1 h-1 rounded-full shrink-0 ${accent.dot}`} />
                  {e}
                </li>
              ))}
            </ul>
          </div>
          <div className="p-6 rounded-2xl border border-white/10 bg-[#0a1628]">
            <h2 className="text-lg font-black text-white mb-5">{ui.categoryAbout.certifications}</h2>
            <ul className="space-y-3">
              {data.certifications.map((c) => (
                <li key={c} className="flex gap-2.5 text-sm text-slate-400 leading-relaxed">
                  <span className={`mt-1.5 w-1 h-1 rounded-full shrink-0 ${accent.dot}`} />
                  {c}
                </li>
              ))}
            </ul>
          </div>
        </motion.div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="text-center p-12 rounded-3xl border border-white/10 bg-gradient-to-br from-sky-950/30 to-[#0a1628]"
        >
          <h2 className="text-3xl font-black text-white mb-3">{ui.categoryAbout.letsWorkTogether}</h2>
          <p className="text-slate-400 mb-8 max-w-md mx-auto">
            {formatTemplate(ui.categoryAbout.ctaBodyTemplate, { role: data.label.toLowerCase() })}
          </p>
          <Link
            href={`/${data.slug}/contact`}
            className="inline-flex items-center gap-2 px-8 py-4 bg-[#38bdf8] text-[#020617] font-bold rounded-xl hover:bg-sky-300 transition-all hover:shadow-lg hover:shadow-sky-400/25"
          >
            {ui.categoryAbout.getInTouch}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
          </Link>
        </motion.div>
      </div>
    </div>
  )
}

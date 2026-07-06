'use client'
import { motion } from 'framer-motion'
import Link from 'next/link'
import type { CategoryData } from '@/lib/resumeData'
import { ACCENT_CLASSES } from '@/lib/resumeData'

export default function CategoryHero({ data }: { data: CategoryData }) {
  const accent = ACCENT_CLASSES[data.accent]

  return (
    <section className="relative pt-40 pb-16 px-6 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-radial from-sky-950/30 via-[#020617] to-[#020617]" />

      <div className="relative max-w-5xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center"
        >
          <span className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold mb-6 ${accent.border} ${accent.bg} ${accent.text}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${accent.dot} animate-pulse`} />
            {data.label} Specialization
          </span>
          <h1 className="text-4xl md:text-6xl font-black text-white mb-4 leading-tight tracking-tight">
            {data.fullTitle}
          </h1>
          <p className="text-slate-400 text-base md:text-lg max-w-2xl mx-auto mb-8 font-medium">{data.tagline}</p>
          <p className="text-slate-400 max-w-2xl mx-auto leading-relaxed mb-10">{data.summary[0]}</p>

          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link
              href={`/${data.slug}/about`}
              className="px-7 py-3.5 bg-gradient-to-r from-[#38bdf8] to-sky-400 text-[#020617] font-extrabold rounded-xl hover:shadow-xl hover:shadow-sky-400/40 active:scale-95 transition-all duration-200"
            >
              Full Background
            </Link>
            <Link
              href={`/${data.slug}/projects`}
              className="px-7 py-3.5 border border-white/20 text-white font-semibold rounded-xl hover:border-[#38bdf8]/60 hover:bg-white/5 hover:text-[#38bdf8] transition-all duration-200 active:scale-95"
            >
              View Projects
            </Link>
            <Link
              href={`/${data.slug}/contact`}
              className="px-7 py-3.5 border border-white/20 text-white font-semibold rounded-xl hover:border-[#38bdf8]/60 hover:bg-white/5 hover:text-[#38bdf8] transition-all duration-200 active:scale-95"
            >
              Contact
            </Link>
          </div>
        </motion.div>

        {/* Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-16"
        >
          {data.heroStats.map((stat) => (
            <div key={stat.label} className="text-center p-5 rounded-2xl border border-white/10 bg-[#0a1628] hover:border-white/20 transition-colors">
              <p className={`text-2xl md:text-3xl font-black mb-1 ${accent.text}`}>{stat.value}</p>
              <p className="text-xs text-slate-500 font-medium leading-snug">{stat.label}</p>
            </div>
          ))}
        </motion.div>

        {/* Top competencies preview */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mt-16"
        >
          <h2 className="text-xl font-black text-white mb-6 text-center">Core Competencies</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.competencies.slice(0, 3).map((group) => (
              <div key={group.category} className="p-5 rounded-2xl border border-white/10 bg-[#0a1628]">
                <h3 className={`text-xs font-bold uppercase tracking-wider mb-3 ${accent.text}`}>{group.category}</h3>
                <div className="flex flex-wrap gap-1.5">
                  {group.items.slice(0, 6).map((skillItem) => (
                    <span key={skillItem} className="px-2.5 py-1 text-[11px] font-medium rounded-md bg-white/5 text-slate-300 border border-white/5">
                      {skillItem}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  )
}

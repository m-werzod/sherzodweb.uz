'use client'
import { motion } from 'framer-motion'

const items = [
  { label: 'Certified Frontend Engineer Expert', sub: 'micro1 (United States) · Proctored', icon: '🏅' },
  { label: 'English — Fluent (C1)', sub: 'IELTS Band 7+', icon: '🇬🇧' },
  { label: '40+ AI APIs Integrated', sub: 'OpenAI · Claude · Gemini · Mistral', icon: '🤖' },
  { label: 'AI-Augmented Delivery', sub: 'Up to 10–20x faster shipping', icon: '⚡' },
]

export default function TrustStrip() {
  return (
    <section className="py-10 px-6 border-y border-white/5 bg-white/[0.015]">
      <div className="max-w-6xl mx-auto grid grid-cols-2 lg:grid-cols-4 gap-4">
        {items.map((item, i) => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: i * 0.08 }}
            className="flex items-center gap-3"
          >
            <span className="text-2xl shrink-0">{item.icon}</span>
            <div className="min-w-0">
              <p className="text-xs sm:text-sm font-bold text-white leading-snug truncate">{item.label}</p>
              <p className="text-[11px] text-slate-500 truncate">{item.sub}</p>
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  )
}

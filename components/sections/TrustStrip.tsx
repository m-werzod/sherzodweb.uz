'use client'
import { motion } from 'framer-motion'
import { useLanguage } from '@/lib/i18n/LanguageContext'

export default function TrustStrip() {
  const { ui } = useLanguage()
  const items = [
    { label: ui.trust.certTitle, sub: ui.trust.certSub, icon: '🏅' },
    { label: ui.trust.englishTitle, sub: ui.trust.englishSub, icon: '🇬🇧' },
    { label: ui.trust.aiApisTitle, sub: ui.trust.aiApisSub, icon: '🤖' },
    { label: ui.trust.aiDeliveryTitle, sub: ui.trust.aiDeliverySub, icon: '⚡' },
  ]

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

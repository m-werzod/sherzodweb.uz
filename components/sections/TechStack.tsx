'use client'
import { motion } from 'framer-motion'

const techs = [
  { name: 'HTML5', color: '#e34f26', bg: 'rgba(227,79,38,0.1)' },
  { name: 'CSS3', color: '#1572b6', bg: 'rgba(21,114,182,0.1)' },
  { name: 'JavaScript', color: '#f7df1e', bg: 'rgba(247,223,30,0.1)' },
  { name: 'TypeScript', color: '#3178c6', bg: 'rgba(49,120,198,0.1)' },
  { name: 'React', color: '#61dafb', bg: 'rgba(97,218,251,0.1)' },
  { name: 'Next.js', color: '#ffffff', bg: 'rgba(255,255,255,0.05)' },
  { name: 'Tailwind CSS', color: '#38bdf8', bg: 'rgba(56,189,248,0.1)' },
  { name: 'Framer Motion', color: '#bb22dd', bg: 'rgba(187,34,221,0.1)' },
  { name: 'Git', color: '#f05032', bg: 'rgba(240,80,50,0.1)' },
  { name: 'Node.js', color: '#339933', bg: 'rgba(51,153,51,0.1)' },
  { name: 'Three.js', color: '#ffffff', bg: 'rgba(255,255,255,0.05)' },
  { name: 'Figma', color: '#f24e1e', bg: 'rgba(242,78,30,0.1)' },
]

const doubled = [...techs, ...techs]

export default function TechStack() {
  return (
    <section className="py-24 overflow-hidden relative">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-sky-950/5 to-transparent pointer-events-none" />

      <div className="max-w-7xl mx-auto px-6 mb-12 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
        >
          <p className="text-xs text-[#38bdf8] font-semibold tracking-[0.25em] uppercase mb-3">Tech Arsenal</p>
          <h2 className="text-3xl md:text-4xl font-black text-white">
            Technologies I <span className="text-[#38bdf8]">Master</span>
          </h2>
        </motion.div>
      </div>

      {/* Marquee row 1 */}
      <div className="relative flex overflow-hidden mb-4 [mask-image:linear-gradient(to_right,transparent,black_15%,black_85%,transparent)]">
        <div className="flex gap-4 animate-marquee whitespace-nowrap">
          {doubled.map((tech, i) => (
            <div
              key={i}
              className="flex items-center gap-2 px-5 py-3 rounded-full border border-white/10 text-sm font-semibold shrink-0 hover:scale-105 transition-transform cursor-default"
              style={{ color: tech.color, background: tech.bg, borderColor: `${tech.color}20` }}
            >
              <span className="w-2 h-2 rounded-full" style={{ background: tech.color }} />
              {tech.name}
            </div>
          ))}
        </div>
      </div>

      {/* Marquee row 2 (reverse) */}
      <div className="relative flex overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_15%,black_85%,transparent)]">
        <div
          className="flex gap-4 whitespace-nowrap"
          style={{ animation: 'marquee 25s linear infinite reverse' }}
        >
          {doubled.map((tech, i) => (
            <div
              key={i}
              className="flex items-center gap-2 px-5 py-3 rounded-full border text-sm font-semibold shrink-0 hover:scale-105 transition-transform cursor-default"
              style={{ color: tech.color, background: tech.bg, borderColor: `${tech.color}20` }}
            >
              <span className="w-2 h-2 rounded-full" style={{ background: tech.color }} />
              {tech.name}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

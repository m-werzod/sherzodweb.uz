'use client'
import { motion } from 'framer-motion'

const DEVICON = 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons'

const techs = [
  { name: 'HTML5',        icon: `${DEVICON}/html5/html5-original.svg` },
  { name: 'CSS3',         icon: `${DEVICON}/css3/css3-original.svg` },
  { name: 'JavaScript',   icon: `${DEVICON}/javascript/javascript-original.svg` },
  { name: 'TypeScript',   icon: `${DEVICON}/typescript/typescript-original.svg` },
  { name: 'React',        icon: `${DEVICON}/react/react-original.svg` },
  { name: 'Next.js',      icon: `${DEVICON}/nextjs/nextjs-original.svg` },
  { name: 'Tailwind CSS', icon: `${DEVICON}/tailwindcss/tailwindcss-original.svg` },
  { name: 'Node.js',      icon: `${DEVICON}/nodejs/nodejs-original.svg` },
  { name: 'Git',          icon: `${DEVICON}/git/git-original.svg` },
  { name: 'Figma',        icon: `${DEVICON}/figma/figma-original.svg` },
  { name: 'Firebase',     icon: `${DEVICON}/firebase/firebase-original.svg` },
  { name: 'Three.js',     icon: `${DEVICON}/threejs/threejs-original.svg` },
]

const doubled = [...techs, ...techs]

function TechPill({ tech }: { tech: typeof techs[0] }) {
  return (
    <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-full border border-white/10 bg-white/[0.03] text-sm font-semibold shrink-0 hover:scale-105 hover:border-white/20 transition-all duration-200 cursor-default select-none">
      <img src={tech.icon} alt={tech.name} className="w-5 h-5 object-contain" loading="lazy" />
      <span className="text-slate-300 whitespace-nowrap">{tech.name}</span>
    </div>
  )
}

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

      {/* Row 1 — left to right */}
      <div className="relative mb-4 [mask-image:linear-gradient(to_right,transparent,black_12%,black_88%,transparent)]">
        <div className="flex gap-3" style={{ animation: 'marquee 14s linear infinite' }}>
          {doubled.map((tech, i) => <TechPill key={i} tech={tech} />)}
        </div>
      </div>

      {/* Row 2 — right to left */}
      <div className="relative [mask-image:linear-gradient(to_right,transparent,black_12%,black_88%,transparent)]">
        <div className="flex gap-3" style={{ animation: 'marquee 20s linear infinite reverse' }}>
          {doubled.map((tech, i) => <TechPill key={i} tech={tech} />)}
        </div>
      </div>
    </section>
  )
}

'use client'
import dynamic from 'next/dynamic'
import { motion } from 'framer-motion'
import Link from 'next/link'
import Image from 'next/image'
import MainImg from '@/app/assets/images/MainImg.jpg'
import { useEffect, useState } from 'react'

// Three.js — only imported if the viewport is ≥ 1024 px
const ThreeScene = dynamic(() => import('./ThreeScene'), {
  ssr: false,
  loading: () => <div className="w-full h-64" />,
})

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.12, delayChildren: 0.15 } },
}
const item = {
  hidden: { y: 24, opacity: 0 },
  show: { y: 0, opacity: 1, transition: { duration: 0.55, ease: 'easeOut' } },
}

const socials = [
  { href: 'https://github.com/m-werzod',                               src: 'https://img.icons8.com/3d-fluency/94/github.png',            alt: 'GitHub'    },
  { href: 'https://t.me/WerzodUsmanov',                                src: 'https://cdn-icons-png.flaticon.com/512/2111/2111646.png',    alt: 'Telegram'  },
  { href: 'https://instagram.com/Sherzod_usmanovv',                    src: 'https://cdn-icons-png.flaticon.com/512/15713/15713420.png',  alt: 'Instagram' },
  { href: 'https://www.linkedin.com/in/sherzod-usmonjonov-8b22713b0/', src: 'https://cdn-icons-png.flaticon.com/512/3992/3992606.png',   alt: 'LinkedIn'  },
]

export default function HeroSection() {
  // Only render ThreeScene on actual desktop — prevents WebGL from executing on mobile
  const [isDesktop, setIsDesktop] = useState(false)
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)')
    setIsDesktop(mq.matches)
    const handler = (e: MediaQueryListEvent) => setIsDesktop(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  return (
    <section className="relative min-h-screen flex items-center overflow-hidden">
      <div className="absolute inset-0 bg-gradient-radial from-sky-950/30 via-[#020617] to-[#020617]" />

      <div className="relative z-10 max-w-7xl mx-auto px-6 w-full grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12 items-center min-h-screen pt-20 pb-12">

        {/* LEFT */}
        <motion.div variants={container} initial="hidden" animate="show" className="flex flex-col gap-5 lg:gap-6">

          {/* 3D Scene — container always rendered (prevents CLS), WebGL only on desktop */}
          <motion.div variants={item} className="hidden lg:block w-full h-64 relative">
            {isDesktop && <ThreeScene />}
          </motion.div>

          {/* Mobile: circular photo */}
          <motion.div variants={item} className="flex flex-col items-center gap-4 lg:hidden pt-6">
            <div className="relative">
              <div className="absolute -inset-1 rounded-full bg-gradient-to-br from-[#38bdf8] via-sky-400 to-indigo-500 opacity-60 blur-sm" />
              <div className="relative w-36 h-36 rounded-full overflow-hidden border-2 border-[#38bdf8]/50 shadow-2xl shadow-sky-900/50">
                <Image
                  src={MainImg}
                  alt="Sherzodbek Usmonjonov"
                  fill
                  priority
                  sizes="144px"
                  className="object-cover object-top"
                />
              </div>
              <span className="absolute bottom-1 right-1 w-4 h-4 rounded-full bg-emerald-400 border-2 border-[#020617] shadow-lg" />
            </div>
            <div className="text-center">
              <h1 className="text-2xl font-black text-white leading-tight">
                Sherzodbek <span className="text-[#38bdf8]">Usmonjonov</span>
              </h1>
              <p className="text-sm font-semibold text-slate-400 mt-1 tracking-wide">Frontend Web Developer</p>
              <div className="inline-flex items-center gap-1.5 mt-2 px-3 py-1 rounded-full border border-[#38bdf8]/30 bg-[#38bdf8]/5 text-[#38bdf8] text-xs font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-[#38bdf8] animate-pulse" />
                Available for Work
              </div>
            </div>
          </motion.div>

          {/* Desktop: badge */}
          <motion.div variants={item} className="hidden lg:inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[#38bdf8]/30 bg-[#38bdf8]/5 text-[#38bdf8] text-xs font-medium w-fit">
            <span className="w-1.5 h-1.5 rounded-full bg-[#38bdf8] animate-pulse" />
            Available for Work
          </motion.div>

          {/* Desktop: heading */}
          <motion.div variants={item} className="hidden lg:block">
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-black leading-tight tracking-tight">
              <span className="block text-white">Sherzodbek</span>
              <span className="block text-[#38bdf8] glow-text">Usmonjonov</span>
            </h1>
            <p className="mt-3 text-lg md:text-xl font-semibold text-slate-400 tracking-wide">Frontend Web Developer</p>
          </motion.div>

          {/* Value prop */}
          <motion.p variants={item} className="text-slate-400 text-sm md:text-base leading-relaxed max-w-md text-center lg:text-left">
            Building{' '}
            <span className="text-[#38bdf8] font-semibold">high-performance web experiences</span>{' '}
            with React &amp; Next.js. Crafting motion designs and 3D visuals with the power of modern AI tools.
          </motion.p>

          {/* Language badges */}
          <motion.div variants={item} className="flex flex-wrap gap-2 justify-center lg:justify-start">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-slate-300">
              <span className="text-base">🇬🇧</span> English — Fluent
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-slate-300">
              <span className="text-base">🇷🇺</span> Russian — Basic
            </span>
          </motion.div>

          {/* CTAs */}
          <motion.div variants={item} className="flex flex-wrap gap-3 justify-center lg:justify-start">
            <Link href="/contact" className="group px-7 py-3.5 bg-gradient-to-r from-[#38bdf8] to-sky-400 text-[#020617] font-extrabold rounded-xl hover:shadow-xl hover:shadow-sky-400/40 active:scale-95 hover:from-sky-300 hover:to-[#38bdf8] flex items-center gap-2 transition-all duration-200">
              <span>Contact Me</span>
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            </Link>
            <Link href="/projects" className="px-7 py-3.5 border border-white/20 text-white font-semibold rounded-xl hover:border-[#38bdf8]/60 hover:bg-white/5 hover:text-[#38bdf8] transition-all duration-200 active:scale-95">
              View Projects
            </Link>
          </motion.div>

          {/* Social icons */}
          <motion.div variants={item} className="flex items-center gap-3 justify-center lg:justify-start">
            {socials.map((s) => (
              <Link key={s.alt} href={s.href} target="_blank" rel="noopener noreferrer"
                className="group w-10 h-10 flex items-center justify-center rounded-xl bg-white/5 border border-white/10 hover:border-[#38bdf8]/40 hover:bg-[#38bdf8]/10 transition-all duration-200">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={s.src} alt={s.alt} width={20} height={20} loading="lazy" decoding="async"
                  className="w-5 h-5 object-contain group-hover:scale-110 transition-transform duration-200" />
              </Link>
            ))}
          </motion.div>

          {/* Mobile scroll indicator */}
          <motion.div variants={item} className="flex lg:hidden flex-col items-center gap-2 pt-2 pb-4">
            <span className="text-[10px] text-slate-600 tracking-[0.3em] uppercase font-medium">Scroll</span>
            <motion.div animate={{ y: [0, 8, 0] }} transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
              className="w-px h-7 bg-gradient-to-b from-[#38bdf8] to-transparent" />
          </motion.div>
        </motion.div>

        {/* RIGHT: Hero image — desktop only */}
        <motion.div initial={{ opacity: 0, x: 50 }} animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: 'easeOut', delay: 0.25 }}
          className="relative hidden lg:flex items-center justify-center py-10">

          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-96 h-96 rounded-full bg-[#38bdf8]/8 blur-3xl" />
          </div>

          <div className="relative w-[380px] h-[540px] rounded-3xl overflow-hidden border border-white/10 shadow-2xl shadow-sky-950/60 bg-[#0a0f1e]">
            <div className="absolute inset-0 bg-gradient-to-t from-[#020617]/70 via-transparent to-transparent z-10 pointer-events-none" />
            <Image src={MainImg} alt="Sherzodbek Usmonjonov" fill priority sizes="380px" className="object-cover object-center" />
          </div>

          {/* Stat cards */}
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0, y: [0, -7, 0] }}
            transition={{ opacity: { duration: 0.5, delay: 0.7 }, x: { duration: 0.5, delay: 0.7 }, y: { duration: 3, repeat: Infinity, ease: 'easeInOut', delay: 1 } }}
            className="absolute left-0 top-[28%] -translate-x-[60%] bg-[#0d1b2e] border border-[#38bdf8]/20 rounded-2xl px-5 py-4 shadow-xl shadow-sky-950/40 backdrop-blur-sm min-w-[130px]">
            <p className="text-3xl font-black text-[#38bdf8] leading-none">1+</p>
            <p className="text-xs text-slate-400 mt-1.5 font-medium">Year Experience</p>
          </motion.div>

          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0, y: [0, 7, 0] }}
            transition={{ opacity: { duration: 0.5, delay: 0.9 }, x: { duration: 0.5, delay: 0.9 }, y: { duration: 3.5, repeat: Infinity, ease: 'easeInOut', delay: 1.2 } }}
            className="absolute right-0 top-[55%] translate-x-[60%] bg-[#0d1b2e] border border-[#38bdf8]/20 rounded-2xl px-5 py-4 shadow-xl shadow-sky-950/40 backdrop-blur-sm min-w-[130px]">
            <p className="text-3xl font-black text-[#38bdf8] leading-none">10+</p>
            <p className="text-xs text-slate-400 mt-1.5 font-medium">Projects Built</p>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: [0, -5, 0] }}
            transition={{ opacity: { duration: 0.5, delay: 1.1 }, y: { duration: 4, repeat: Infinity, ease: 'easeInOut', delay: 1.4 } }}
            className="absolute left-[10%] bottom-[4%] bg-[#0d1b2e] border border-[#38bdf8]/20 rounded-2xl px-5 py-4 shadow-xl shadow-sky-950/40 backdrop-blur-sm min-w-[130px]">
            <p className="text-3xl font-black text-[#38bdf8] leading-none">15+</p>
            <p className="text-xs text-slate-400 mt-1.5 font-medium">Technologies</p>
          </motion.div>
        </motion.div>
      </div>

      {/* Desktop scroll indicator */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.3 }}
        className="hidden lg:flex absolute bottom-8 left-1/2 -translate-x-1/2 flex-col items-center gap-2">
        <span className="text-xs text-slate-600 tracking-widest uppercase">Scroll</span>
        <motion.div animate={{ y: [0, 8, 0] }} transition={{ duration: 1.5, repeat: Infinity }}
          className="w-px h-8 bg-gradient-to-b from-[#38bdf8] to-transparent" />
      </motion.div>
    </section>
  )
}

'use client'
import dynamic from 'next/dynamic'
import { motion } from 'framer-motion'
import Link from 'next/link'
import { useState, useEffect, useRef } from 'react'

const ThreeScene = dynamic(() => import('./ThreeScene'), { ssr: false })

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.15, delayChildren: 0.3 },
  },
}

const item = {
  hidden: { y: 30, opacity: 0 },
  show: { y: 0, opacity: 1, transition: { duration: 0.7, ease: 'easeOut' } },
}

export default function HeroSection() {
  const [imgLoaded, setImgLoaded] = useState(false)
  const [imgError, setImgError] = useState(false)
  const imgRef = useRef<HTMLImageElement>(null)
  const imgRef2 = useRef<HTMLImageElement>(null)

  // Handle cached images that fire onLoad before React attaches the handler
  useEffect(() => {
    if (imgRef.current?.complete) setImgLoaded(true)
    if (imgRef2.current?.complete) setImgLoaded(true)
  }, [])

  return (
    <section className="relative min-h-screen flex items-center overflow-hidden">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-radial from-sky-950/30 via-[#020617] to-[#020617]" />

      <div className="relative z-10 max-w-7xl mx-auto px-6 w-full grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12 items-center min-h-screen pt-20 pb-12">

        {/* LEFT: Text + 3D */}
        <motion.div variants={container} initial="hidden" animate="show" className="flex flex-col gap-5 lg:gap-6">

          {/* 3D Scene — hidden on mobile to save space */}
          <motion.div variants={item} className="hidden lg:block w-full h-64 relative">
            <ThreeScene />
          </motion.div>

          {/* Mobile: Photo + Name block */}
          <motion.div
            variants={item}
            className="flex flex-col items-center gap-4 lg:hidden pt-6"
          >
            {/* Circle photo */}
            <div className="relative">
              {/* Glow ring */}
              <div className="absolute -inset-1 rounded-full bg-gradient-to-br from-[#38bdf8] via-sky-400 to-indigo-500 opacity-60 blur-sm" />
              <div className="relative w-36 h-36 rounded-full overflow-hidden border-2 border-[#38bdf8]/50 shadow-2xl shadow-sky-900/50">
                {!imgError ? (
                  <img
                    ref={imgRef}
                    src="/images/hero2.png"
                    alt="Sherzodbek Usmonjonov"
                    onLoad={() => setImgLoaded(true)}
                    onError={() => setImgError(true)}
                    className={`w-full h-full object-cover object-center transition-opacity duration-500 ${imgLoaded ? 'opacity-100' : 'opacity-0'}`}
                  />
                ) : (
                  <div className="w-full h-full bg-gradient-to-br from-slate-700 to-slate-900 flex items-center justify-center">
                    <span className="text-4xl font-black text-[#38bdf8]">SU</span>
                  </div>
                )}
              </div>
              {/* Online dot */}
              <span className="absolute bottom-1 right-1 w-4 h-4 rounded-full bg-emerald-400 border-2 border-[#020617] shadow-lg" />
            </div>

            {/* Name + title under circle (mobile) */}
            <div className="text-center">
              <h1 className="text-2xl font-black text-white leading-tight">
                Sherzodbek <span className="text-[#38bdf8]">Usmonjonov</span>
              </h1>
              <p className="text-sm font-semibold text-slate-400 mt-1 tracking-wide">
                Frontend Web Developer
              </p>
              <div className="inline-flex items-center gap-1.5 mt-2 px-3 py-1 rounded-full border border-[#38bdf8]/30 bg-[#38bdf8]/5 text-[#38bdf8] text-xs font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-[#38bdf8] animate-pulse" />
                Available for Work
              </div>
            </div>
          </motion.div>

          {/* Desktop: Available badge */}
          <motion.div
            variants={item}
            className="hidden lg:inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[#38bdf8]/30 bg-[#38bdf8]/5 text-[#38bdf8] text-xs font-medium w-fit"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[#38bdf8] animate-pulse" />
            Available for Work
          </motion.div>

          {/* Desktop: Main heading */}
          <motion.div variants={item} className="hidden lg:block">
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-black leading-tight tracking-tight">
              <span className="block text-white">Sherzodbek</span>
              <span className="block text-[#38bdf8] glow-text">Usmonjonov</span>
            </h1>
            <p className="mt-3 text-lg md:text-xl font-semibold text-slate-400 tracking-wide">
              Frontend Web Developer
            </p>
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
              <span className="text-base">🇷🇺</span> Russian — basic
            </span>
          </motion.div>

          {/* CTAs */}
          <motion.div variants={item} className="flex flex-wrap gap-3 justify-center lg:justify-start">
            <Link
              href="/projects"
              className="px-6 py-3 bg-[#38bdf8] text-[#020617] font-bold rounded-xl hover:bg-sky-300 transition-all duration-200 hover:shadow-lg hover:shadow-sky-400/25 active:scale-95"
            >
              View Projects
            </Link>
            <Link
              href="/contact"
              className="px-6 py-3 border border-white/15 text-white font-semibold rounded-xl hover:border-[#38bdf8]/50 hover:bg-white/5 transition-all duration-200 active:scale-95"
            >
              Contact Me
            </Link>
          </motion.div>

          {/* Social icons */}
          <motion.div variants={item} className="flex items-center gap-3 justify-center lg:justify-start">
            {[
              {
                href: 'https://github.com/m-werzod',
                src: 'https://img.icons8.com/3d-fluency/94/github.png',
                alt: 'GitHub',
              },
              {
                href: 'https://t.me/WerzodUsmanov',
                src: 'https://cdn-icons-png.flaticon.com/512/2111/2111646.png',
                alt: 'Telegram',
              },
              {
                href: 'https://instagram.com/Sherzod_usmanovv',
                src: 'https://cdn-icons-png.flaticon.com/512/15713/15713420.png',
                alt: 'Instagram',
              },
              {
                href: 'https://www.linkedin.com/in/sherzod-usmonjonov-8b22713b0/',
                src: 'https://cdn-icons-png.flaticon.com/512/3992/3992606.png',
                alt: 'LinkedIn',
              },
            ].map((s) => (
              <Link
                key={s.alt}
                href={s.href}
                target="_blank"
                rel="noopener noreferrer"
                className="group w-10 h-10 flex items-center justify-center rounded-xl bg-white/5 border border-white/10 hover:border-[#38bdf8]/40 hover:bg-[#38bdf8]/10 transition-all duration-200"
              >
                <img
                  src={s.src}
                  alt={s.alt}
                  className="w-5 h-5 object-contain group-hover:scale-110 transition-transform duration-200"
                />
              </Link>
            ))}
          </motion.div>

          {/* ── Mobile scroll indicator (under social icons) ── */}
          <motion.div
            variants={item}
            className="flex lg:hidden flex-col items-center gap-2 pt-2 pb-4"
          >
            <span className="text-[10px] text-slate-600 tracking-[0.3em] uppercase font-medium">Scroll</span>
            <motion.div
              animate={{ y: [0, 8, 0] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
              className="w-px h-7 bg-gradient-to-b from-[#38bdf8] to-transparent"
            />
          </motion.div>
        </motion.div>

        {/* RIGHT: Hero Image — desktop only */}
        <motion.div
          initial={{ opacity: 0, x: 60 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.9, ease: 'easeOut', delay: 0.4 }}
          className="relative hidden lg:flex items-center justify-center py-10"
        >
          {/* Ambient glow blob */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-96 h-96 rounded-full bg-[#38bdf8]/8 blur-3xl" />
          </div>

          {/* ── Image frame ── */}
          <div className="relative w-[380px] h-[540px] rounded-3xl overflow-hidden border border-white/10 shadow-2xl shadow-sky-950/60 bg-[#0a0f1e]">
            {/* Bottom-to-top dark fade so the image merges into the page */}
            <div className="absolute inset-0 bg-gradient-to-t from-[#020617]/70 via-transparent to-transparent z-10 pointer-events-none" />

            {!imgError ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                ref={imgRef2}
                src="/images/hero2.png"
                alt="Sherzodbek Usmonjonov"
                onLoad={() => setImgLoaded(true)}
                onError={() => setImgError(true)}
                className={`absolute inset-0 w-full h-full object-cover object-center transition-opacity duration-500 ${
                  imgLoaded ? 'opacity-100' : 'opacity-0'
                }`}
              />
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
                <span className="text-5xl font-black text-[#38bdf8]/30">SU</span>
              </div>
            )}
          </div>

          {/* ── Stat card — LEFT (overlaps left edge, upper-third) ── */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0, y: [0, -7, 0] }}
            transition={{
              opacity: { duration: 0.5, delay: 0.8 },
              x:       { duration: 0.5, delay: 0.8 },
              y:       { duration: 3, repeat: Infinity, ease: 'easeInOut', delay: 1 },
            }}
            className="absolute left-0 top-[28%] -translate-x-[60%] bg-[#0d1b2e] border border-[#38bdf8]/20 rounded-2xl px-5 py-4 shadow-xl shadow-sky-950/40 backdrop-blur-sm min-w-[130px]"
          >
            <p className="text-3xl font-black text-[#38bdf8] leading-none">1+</p>
            <p className="text-xs text-slate-400 mt-1.5 font-medium">Year Experience</p>
          </motion.div>

          {/* ── Stat card — RIGHT (overlaps right edge, lower-half) ── */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0, y: [0, 7, 0] }}
            transition={{
              opacity: { duration: 0.5, delay: 1 },
              x:       { duration: 0.5, delay: 1 },
              y:       { duration: 3.5, repeat: Infinity, ease: 'easeInOut', delay: 1.2 },
            }}
            className="absolute right-0 top-[55%] translate-x-[60%] bg-[#0d1b2e] border border-[#38bdf8]/20 rounded-2xl px-5 py-4 shadow-xl shadow-sky-950/40 backdrop-blur-sm min-w-[130px]"
          >
            <p className="text-3xl font-black text-[#38bdf8] leading-none">10+</p>
            <p className="text-xs text-slate-400 mt-1.5 font-medium">Projects Built</p>
          </motion.div>

          {/* ── Stat card — BOTTOM-LEFT (tech count) ── */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: [0, -5, 0] }}
            transition={{
              opacity: { duration: 0.5, delay: 1.2 },
              y:       { duration: 4, repeat: Infinity, ease: 'easeInOut', delay: 1.4 },
            }}
            className="absolute left-[10%] bottom-[4%] bg-[#0d1b2e] border border-[#38bdf8]/20 rounded-2xl px-5 py-4 shadow-xl shadow-sky-950/40 backdrop-blur-sm min-w-[130px]"
          >
            <p className="text-3xl font-black text-[#38bdf8] leading-none">15+</p>
            <p className="text-xs text-slate-400 mt-1.5 font-medium">Technologies</p>
          </motion.div>
        </motion.div>
      </div>

      {/* Scroll indicator — desktop only, absolute bottom-center */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.5 }}
        className="hidden lg:flex absolute bottom-8 left-1/2 -translate-x-1/2 flex-col items-center gap-2"
      >
        <span className="text-xs text-slate-600 tracking-widest uppercase">Scroll</span>
        <motion.div
          animate={{ y: [0, 8, 0] }}
          transition={{ duration: 1.5, repeat: Infinity }}
          className="w-px h-8 bg-gradient-to-b from-[#38bdf8] to-transparent"
        />
      </motion.div>
    </section>
  )
}

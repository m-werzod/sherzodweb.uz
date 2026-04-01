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
                    src="/images/hero.png"
                    alt="Sherzodbek Usmonjonov"
                    onLoad={() => setImgLoaded(true)}
                    onError={() => setImgError(true)}
                    className={`w-full h-full object-cover object-top transition-opacity duration-500 ${imgLoaded ? 'opacity-100' : 'opacity-0'}`}
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
              <span className="text-base">🇷🇺</span> Russian — Understands
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
                href: '#',
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
        </motion.div>

        {/* RIGHT: Hero Image — desktop only */}
        <motion.div
          initial={{ opacity: 0, x: 60 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.9, ease: 'easeOut', delay: 0.4 }}
          className="relative hidden lg:flex items-center justify-center"
        >
          {/* Glow blob behind image */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-80 h-80 rounded-full bg-[#38bdf8]/10 blur-3xl" />
          </div>

          {/* Image container */}
          <div className="relative w-[360px] h-[500px] rounded-3xl overflow-hidden border border-white/10 shadow-2xl shadow-sky-950/50 bg-gradient-to-b from-slate-800 to-[#020617]">
            {/* Subtle dark overlays to blend edges */}
            <div className="absolute inset-0 bg-gradient-to-t from-[#020617]/50 via-transparent to-transparent z-10" />
            <div className="absolute inset-0 bg-gradient-to-r from-[#020617]/20 via-transparent to-transparent z-10" />

            {!imgError ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                ref={imgRef2}
                src="/images/hero.png"
                alt="Sherzodbek Usmonjonov"
                onLoad={() => setImgLoaded(true)}
                onError={() => setImgError(true)}
                className={`absolute inset-0 w-full h-full object-cover object-top transition-opacity duration-500 ${
                  imgLoaded ? 'opacity-100' : 'opacity-0'
                }`}
              />
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
                <div className="w-24 h-24 rounded-full bg-gradient-to-br from-slate-600 to-slate-800 flex items-center justify-center">
                  <span className="text-4xl font-black text-[#38bdf8]">SU</span>
                </div>
                <p className="text-slate-500 text-sm">Add hero.jpg to /public/images/</p>
              </div>
            )}
          </div>

          {/* Floating stat — left */}
          <motion.div
            animate={{ y: [0, -8, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
            className="absolute -left-6 top-1/4 bg-[#0f172a] border border-white/10 rounded-2xl p-4 shadow-xl backdrop-blur-sm"
          >
            <p className="text-2xl font-black text-[#38bdf8]">1+</p>
            <p className="text-xs text-slate-400 mt-0.5">Year Experience</p>
          </motion.div>

          {/* Floating stat — right */}
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 3.5, repeat: Infinity, ease: 'easeInOut', delay: 0.5 }}
            className="absolute -right-6 bottom-1/3 bg-[#0f172a] border border-white/10 rounded-2xl p-4 shadow-xl backdrop-blur-sm"
          >
            <p className="text-2xl font-black text-[#38bdf8]">10+</p>
            <p className="text-xs text-slate-400 mt-0.5">Projects Built</p>
          </motion.div>
        </motion.div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.5 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2"
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

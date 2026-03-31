'use client'
import dynamic from 'next/dynamic'
import { motion } from 'framer-motion'
import Link from 'next/link'
import Image from 'next/image'

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
  return (
    <section className="relative min-h-screen flex items-center overflow-hidden">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-radial from-sky-950/30 via-[#020617] to-[#020617]" />

      <div className="relative z-10 max-w-7xl mx-auto px-6 w-full grid grid-cols-1 lg:grid-cols-2 gap-12 items-center min-h-screen pt-20 pb-12">

        {/* LEFT: Text + 3D */}
        <motion.div variants={container} initial="hidden" animate="show" className="flex flex-col gap-6">

          {/* 3D Scene */}
          <motion.div variants={item} className="w-full h-48 lg:h-64 relative">
            <ThreeScene />
          </motion.div>

          {/* Badge */}
          <motion.div
            variants={item}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[#38bdf8]/30 bg-[#38bdf8]/5 text-[#38bdf8] text-xs font-medium w-fit"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[#38bdf8] animate-pulse" />
            Available for Work
          </motion.div>

          {/* Main heading */}
          <motion.div variants={item}>
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-black leading-tight tracking-tight">
              <span className="block text-white">Sherzodbek</span>
              <span className="block text-[#38bdf8] glow-text">Usmonjonov</span>
            </h1>
            <p className="mt-3 text-lg md:text-xl font-semibold text-slate-400 tracking-wide">
              Frontend Web Developer
            </p>
          </motion.div>

          {/* Value prop */}
          <motion.p variants={item} className="text-slate-400 text-base leading-relaxed max-w-md">
            Frontend Architect Crafting{' '}
            <span className="text-[#38bdf8] font-semibold">High-Performance Digital Experiences.</span>{' '}
            Specializing in React, Next.js, and modern web technologies.
          </motion.p>

          {/* CTAs */}
          <motion.div variants={item} className="flex flex-wrap gap-4">
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
          <motion.div variants={item} className="flex items-center gap-4">
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

        {/* RIGHT: Hero Image */}
        <motion.div
          initial={{ opacity: 0, x: 60 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.9, ease: 'easeOut', delay: 0.4 }}
          className="relative hidden lg:flex items-center justify-center"
        >
          {/* Glow blob behind image */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-80 h-80 rounded-full bg-[#38bdf8]/10 blur-3xl" />
          </div>

          {/* Image container */}
          <div className="relative w-[380px] h-[520px] rounded-3xl overflow-hidden border border-white/10 shadow-2xl shadow-sky-950/50">
            {/* Dark gradient overlay */}
            <div className="absolute inset-0 bg-gradient-to-t from-[#020617] via-transparent to-transparent z-10 opacity-40" />
            <div className="absolute inset-0 bg-gradient-to-r from-[#020617]/30 via-transparent to-transparent z-10" />

            <Image
              src="/images/hero.jpg"
              alt="Sherzodbek Usmonjonov"
              fill
              className="object-cover object-top"
              priority
            />
          </div>

          {/* Floating stats cards */}
          <motion.div
            animate={{ y: [0, -8, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
            className="absolute -left-4 top-1/4 bg-[#0f172a] border border-white/10 rounded-2xl p-4 shadow-xl backdrop-blur-sm"
          >
            <p className="text-2xl font-black text-[#38bdf8]">2+</p>
            <p className="text-xs text-slate-400 mt-0.5">Years Experience</p>
          </motion.div>

          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 3.5, repeat: Infinity, ease: 'easeInOut', delay: 0.5 }}
            className="absolute -right-4 bottom-1/3 bg-[#0f172a] border border-white/10 rounded-2xl p-4 shadow-xl backdrop-blur-sm"
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

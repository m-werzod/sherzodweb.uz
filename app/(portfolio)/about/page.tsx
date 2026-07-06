'use client'
import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import Link from 'next/link'

const skills = [
  { category: 'Frontend', items: ['React 19', 'Next.js', 'TypeScript', 'Tailwind CSS', 'Framer Motion', 'Three.js'] },
  { category: 'Backend & Databases', items: ['Node.js', 'Express', 'PostgreSQL', 'Prisma ORM', 'REST APIs'] },
  { category: 'AI & Automation', items: ['OpenAI / Claude / Gemini APIs', 'Prompt Engineering', 'Claude Code', 'n8n Automation'] },
  { category: 'Tools & Platforms', items: ['Git', 'Figma', 'Vercel', 'Docker (Basics)'] },
]

const services = [
  {
    title: 'Frontend Development',
    desc: 'Building pixel-perfect, responsive web applications with JS, React and Next.js . Every component is crafted with performance and maintainability in mind.',
    iconSrc: 'https://cdn-icons-png.flaticon.com/512/1005/1005141.png',
  },
  {
    title: 'Motion Design & 3D and AI powered Web Experiences',
    desc: 'Creating smooth animations, cinematic transitions, and immersive 3D web experiences using Framer Motion, Three.js, with AI-powered tools.',
    iconSrc: 'https://cdn-icons-png.flaticon.com/512/3898/3898082.png',
  },
  {
    title: 'UI/UX Implementation',
    desc: 'Translating Figma designs into living, breathing interfaces with micro-interactions, animated feedback, and delightful user experiences.',
    iconSrc: 'https://cdn-icons-png.flaticon.com/512/5956/5956592.png',
  },
]

const languages = [
  { lang: 'Uzbek', level: 'Native', flag: 'https://flagcdn.com/w80/uz.png', fill: 100 },
  { lang: 'English', level: 'Fluent — C1, IELTS Band 7+', flag: 'https://flagcdn.com/w80/gb.png', fill: 90 },
  { lang: 'Russian', level: 'Conversational', flag: 'https://flagcdn.com/w80/ru.png', fill: 45 },
]

export default function AboutPage() {
  const [imgError, setImgError] = useState(false)
  const [imgLoaded, setImgLoaded] = useState(false)
  const imgRef = useRef<HTMLImageElement>(null)
  useEffect(() => { if (imgRef.current?.complete) setImgLoaded(true) }, [])

  return (
    <div className="min-h-screen pt-36 pb-24 px-6">
      <div className="max-w-5xl mx-auto">
        {/* Hero */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-20"
        >
          <p className="text-xs text-[#38bdf8] font-semibold tracking-[0.25em] uppercase mb-3">
            About Me
          </p>
          <h1 className="text-4xl md:text-5xl font-black text-white mb-6">
            Full-Stack Engineer, <span className="text-[#38bdf8]">AI-Augmented</span>
          </h1>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-4 text-slate-400 leading-relaxed">
              <p>
                I&apos;m{" "}
                <span className="text-white font-semibold">
                  Sherzodbek Usmonjonov
                </span>
                , a{" "}
                <span className="text-[#38bdf8] font-semibold">
                  Full-Stack Developer
                </span>{" "}
                from Uzbekistan, internationally certified as a Frontend Engineer Expert
                by micro1 (United States). I build production web applications end to
                end — React 19 &amp; Next.js frontends on Node.js and PostgreSQL/Prisma
                backends.
              </p>
              <p>
                I independently architected and ship{" "}
                <span className="text-white font-medium">Era AI</span>, a full-stack
                platform integrating 40+ AI tools behind one unified interface, and
                delivered the{" "}
                <span className="text-white font-medium">Labour Migration Agency</span>{" "}
                platform end to end. I run an{" "}
                <span className="text-white font-medium">AI-augmented workflow</span>{" "}
                with Claude Code and prompt engineering to ship senior-level quality
                up to 10x faster.
              </p>
              <p>
                I believe great software lives at the intersection of{" "}
                <span className="text-[#38bdf8]">technical excellence</span> and{" "}
                <span className="text-[#38bdf8]">creative vision</span>. Fluent in
                English (C1, IELTS 7+), I&apos;m always exploring new tools,
                frameworks, and techniques to stay ahead of the curve.
              </p>
            </div>

            {/* Photo */}
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.7, delay: 0.2 }}
              className="relative flex justify-center lg:justify-end"
            >
              {/* Glow blob */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="w-64 h-64 rounded-full bg-[#38bdf8]/10 blur-3xl" />
              </div>

              {/* Portrait frame */}
              <div className="relative w-full max-w-[340px] h-[480px] md:h-[540px] rounded-3xl overflow-hidden border border-white/10 shadow-2xl shadow-sky-950/40 bg-gradient-to-b from-slate-800/40 to-[#020617]">
                {/* Gradient overlay — blends the dark photo bg seamlessly */}
                <div className="absolute inset-0 bg-gradient-to-t from-[#020617]/50 via-transparent to-transparent z-10 pointer-events-none" />
                <div className="absolute inset-0 bg-gradient-to-r from-[#020617]/20 via-transparent to-[#020617]/20 z-10 pointer-events-none" />

                {!imgError ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    ref={imgRef}
                    src="/images/about.webp"
                    alt="Sherzodbek Usmonjonov"
                    onLoad={() => setImgLoaded(true)}
                    onError={() => setImgError(true)}
                    className={`absolute inset-0 w-full h-full object-cover object-center transition-opacity duration-500 ${
                      imgLoaded ? "opacity-100" : "opacity-0"
                    }`}
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-6xl font-black text-[#38bdf8]/30">SU</span>
                  </div>
                )}

                {/* Name badge at the bottom */}
                <div className="absolute bottom-0 left-0 right-0 z-20 p-5 bg-gradient-to-t from-[#020617] via-[#020617]/80 to-transparent">
                  <p className="text-base font-bold text-white tracking-tight">Sherzodbek Usmonjonov</p>
                  <p className="text-xs text-[#38bdf8] font-medium mt-0.5">Frontend Web Developer</p>
                </div>
              </div>
            </motion.div>
          </div>
        </motion.div>

        {/* Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-20"
        >
          {[
            { label: "Live Platforms Shipped", value: "5+" },
            { label: "AI APIs Integrated", value: "40+" },
            { label: "Lighthouse Score", value: "98/100" },
            { label: "Faster w/ AI-Augmented Delivery", value: "10x" },
          ].map((stat) => (
            <div
              key={stat.label}
              className="text-center p-6 rounded-2xl border border-white/10 bg-[#0a1628] hover:border-[#38bdf8]/30 transition-colors"
            >
              <p className="text-3xl font-black text-[#38bdf8] mb-1">
                {stat.value}
              </p>
              <p className="text-xs text-slate-500 font-medium">{stat.label}</p>
            </div>
          ))}
        </motion.div>

        {/* Skills */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mb-20"
        >
          <h2 className="text-2xl font-black text-white mb-8">
            Technical Skills
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {skills.map((group) => (
              <div
                key={group.category}
                className="p-6 rounded-2xl border border-white/10 bg-[#0a1628]"
              >
                <h3 className="text-sm font-bold text-[#38bdf8] uppercase tracking-wider mb-4">
                  {group.category}
                </h3>
                <div className="flex flex-wrap gap-2">
                  {group.items.map((skill) => (
                    <span
                      key={skill}
                      className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white/5 text-slate-300 border border-white/5"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
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
          <h2 className="text-2xl font-black text-white mb-8">Languages</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {languages.map((l, i) => (
              <motion.div
                key={l.lang}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="p-5 rounded-2xl border border-white/10 bg-[#0a1628] hover:border-[#38bdf8]/30 transition-all"
              >
                <div className="flex items-center gap-3 mb-3">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={l.flag} alt={`${l.lang} flag`} className="w-8 h-6 rounded object-cover shrink-0 border border-white/10" />
                  <div>
                    <p className="text-sm font-bold text-white">{l.lang}</p>
                    <p className="text-xs text-slate-500">{l.level}</p>
                  </div>
                </div>
                <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    whileInView={{ width: `${l.fill}%` }}
                    viewport={{ once: true }}
                    transition={{
                      duration: 1,
                      delay: i * 0.15,
                      ease: "easeOut",
                    }}
                    className="h-full rounded-full bg-gradient-to-r from-[#38bdf8] to-sky-300"
                  />
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Certifications */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mb-20"
        >
          <h2 className="text-2xl font-black text-white mb-8">Certifications</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { title: 'Frontend Engineer Expert Certification', org: 'micro1 (United States) — 2026', badge: '✓ Independently Proctored' },
              { title: "Frontend Engineering Program", org: "Najot Ta'lim — 2025–2026, Graduated", badge: null },
              { title: 'AI & Prompt Engineering for Developers', org: "Najot Ta'lim — 2026", badge: null },
              { title: 'IELTS — Band 7+', org: 'C1 Advanced English', badge: null },
            ].map((cert) => (
              <div key={cert.title} className="flex items-start gap-3 p-4 rounded-2xl border border-white/10 bg-[#0a1628] hover:border-[#38bdf8]/30 transition-all">
                <div className="w-9 h-9 rounded-xl bg-[#38bdf8]/10 flex items-center justify-center shrink-0 mt-0.5">
                  <svg className="w-4 h-4 text-[#38bdf8]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 15a4 4 0 100-8 4 4 0 000 8z"/><path d="M8.21 13.89L7 23l5-3 5 3-1.21-9.12"/>
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-bold text-white leading-snug">{cert.title}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{cert.org}</p>
                  {cert.badge && <p className="text-[10px] text-emerald-400 font-semibold mt-1">{cert.badge}</p>}
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Services */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mb-20"
        >
          <h2 className="text-2xl font-black text-white mb-8">What I Do</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {services.map((service, i) => (
              <motion.div
                key={service.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="p-6 rounded-2xl border border-white/10 bg-[#0a1628] hover:border-[#38bdf8]/30 transition-all group"
              >
                <div className="w-10 h-10 rounded-xl bg-[#38bdf8]/10 flex items-center justify-center mb-4 group-hover:bg-[#38bdf8]/20 transition-colors">
                  <img
                    src={service.iconSrc}
                    alt={service.title}
                    className="w-5 h-5 object-contain"
                  />
                </div>
                <h3 className="text-base font-bold text-white group-hover:text-[#38bdf8] transition-colors mb-3">
                  {service.title}
                </h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  {service.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="text-center p-12 rounded-3xl border border-white/10 bg-gradient-to-br from-sky-950/30 to-[#0a1628]"
        >
          <h2 className="text-3xl font-black text-white mb-3">
            Let&apos;s Work Together
          </h2>
          <p className="text-slate-400 mb-8 max-w-md mx-auto">
            Have a project in mind? I&apos;m available for freelance work and
            open to full-time opportunities.
          </p>
          <Link
            href="/contact"
            className="inline-flex items-center gap-2 px-8 py-4 bg-[#38bdf8] text-[#020617] font-bold rounded-xl hover:bg-sky-300 transition-all hover:shadow-lg hover:shadow-sky-400/25"
          >
            Get In Touch
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 8l4 4m0 0l-4 4m4-4H3"
              />
            </svg>
          </Link>
        </motion.div>
      </div>
    </div>
  );
}

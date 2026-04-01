'use client'
import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import Link from 'next/link'

const skills = [
  { category: 'Frontend', items: ['React', 'Next.js', 'TypeScript', 'JS', 'Tailwind CSS', 'CSS', 'Framer Motion with AI'] },
  { category: '3D & Motion Designs with AI', items: ['Three.js (AI-assisted)', 'React Three Fiber', 'Motion Design', 'CSS Animations'] },
  { category: 'Tools & Others', items: ['Git', 'Figma', 'Node.js', 'Vercel'] },
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
  { lang: 'English', level: 'Fluent — speaks freely', flag: 'EN', fill: 95 },
  { lang: 'Russian', level: 'Understands basic, speaks barely', flag: '🇷🇺', fill: 35 },
  { lang: 'Uzbek', level: 'Native', flag: '🇺🇿', fill: 100 },
]

export default function AboutPage() {
  const [imgError, setImgError] = useState(false)
  const [imgLoaded, setImgLoaded] = useState(false)
  const imgRef = useRef<HTMLImageElement>(null)
  useEffect(() => { if (imgRef.current?.complete) setImgLoaded(true) }, [])

  return (
    <div className="min-h-screen pt-28 pb-24 px-6">
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
            Passionate about <span className="text-[#38bdf8]">the web</span>
          </h1>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
            <div className="space-y-4 text-slate-400 leading-relaxed">
              <p>
                I&apos;m{" "}
                <span className="text-white font-semibold">
                  Sherzodbek Usmonjonov
                </span>
                , a{" "}
                <span className="text-[#38bdf8] font-semibold">
                  Frontend Web Developer
                </span>{" "}
                from Uzbekistan with a passion for building exceptional digital
                experiences. I specialize in transforming complex ideas into
                elegant, high-performance web applications.
              </p>
              <p>
                My journey started with pure curiosity — tinkering with HTML and
                CSS, then discovering the power of JavaScript. Over the past
                year I&apos;ve built full-scale React &amp; Next.js apps. Plus,
                I am learning <span className="text-white font-medium">Prompt engineering</span> and the{" "}
                <span className="text-white font-medium">AI automation</span>{" "} and want ot integrate it into my workflow
                and I also bring interfaces to life through{" "}
                <span className="text-white font-medium">motion design</span>{" "}
                and{" "}
                <span className="text-white font-medium">
                  3D web experiences
                </span>
                , leveraging modern AI tools to push creative boundaries.
              </p>
              <p>
                I believe great software lives at the intersection of{" "}
                <span className="text-[#38bdf8]">technical excellence</span> and{" "}
                <span className="text-[#38bdf8]">creative vision</span>.
                I&apos;m always exploring new tools, frameworks, and techniques
                to stay ahead of the curve.
              </p>
            </div>

            {/* Photo */}
            <div className="relative h-80 rounded-2xl overflow-hidden border border-white/10 bg-gradient-to-b from-slate-800 to-[#020617]">
              <div className="absolute inset-0 bg-gradient-to-t from-[#020617]/60 via-transparent to-transparent z-10" />
              {!imgError ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  ref={imgRef}
                  src="/images/hero.png"
                  alt="Sherzodbek Usmonjonov"
                  onLoad={() => setImgLoaded(true)}
                  onError={() => setImgError(true)}
                  className={`absolute inset-0 w-full h-full object-cover object-top transition-opacity duration-500 ${
                    imgLoaded ? "opacity-100" : "opacity-0"
                  }`}
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-6xl font-black text-[#38bdf8]/30">
                    SU
                  </span>
                </div>
              )}
            </div>
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
            { label: "Year Experience", value: "1+" },
            { label: "Projects Built", value: "10+" },
            { label: "Technologies", value: "15+" },
            { label: "Lighthouse Score", value: "95+" },
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
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
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
                  <span className="text-2xl">{l.flag}</span>
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

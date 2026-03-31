'use client'
import { motion } from 'framer-motion'
import Image from 'next/image'
import Link from 'next/link'

const skills = [
  { category: 'Frontend', items: ['React', 'Next.js 14', 'TypeScript', 'Tailwind CSS', 'Framer Motion'] },
  { category: '3D & Animation', items: ['Three.js', 'React Three Fiber', 'GSAP', 'CSS Animations'] },
  { category: 'Tools & Others', items: ['Git', 'Figma', 'Node.js', 'Firebase', 'Vercel'] },
]

const services = [
  {
    title: 'Frontend Development',
    desc: 'Building pixel-perfect, responsive web applications with React and Next.js. Every component is crafted with performance and maintainability in mind.',
    icon: '⚡',
  },
  {
    title: 'UI/UX Implementation',
    desc: 'Translating Figma designs into living, breathing interfaces with micro-interactions, animations, and delightful user experiences.',
    icon: '🎨',
  },
  {
    title: 'Performance Optimization',
    desc: 'Auditing and optimizing web apps for Core Web Vitals — achieving 95+ Lighthouse scores through code splitting, lazy loading, and caching strategies.',
    icon: '🚀',
  },
]

export default function AboutPage() {
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
          <p className="text-xs text-[#38bdf8] font-semibold tracking-[0.25em] uppercase mb-3">About Me</p>
          <h1 className="text-4xl md:text-5xl font-black text-white mb-6">
            Passionate about <span className="text-[#38bdf8]">the web</span>
          </h1>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
            <div className="space-y-4 text-slate-400 leading-relaxed">
              <p>
                I&apos;m <span className="text-white font-semibold">Sherzodbek Usmonjonov</span>, a Frontend Architect from
                Uzbekistan with a passion for building exceptional digital experiences. I specialize in transforming complex
                ideas into elegant, high-performance web applications.
              </p>
              <p>
                My journey in web development started with pure curiosity — tinkering with HTML and CSS, then discovering
                the power of JavaScript. Today, I architect full-scale React and Next.js applications, leveraging
                cutting-edge tools to deliver production-ready products.
              </p>
              <p>
                When I&apos;m not coding, I&apos;m exploring 3D web experiences, studying design systems, and contributing to
                open-source projects. I believe great software is born at the intersection of{' '}
                <span className="text-[#38bdf8]">technical excellence</span> and{' '}
                <span className="text-[#38bdf8]">creative vision</span>.
              </p>
            </div>

            <div className="relative h-80 rounded-2xl overflow-hidden border border-white/10">
              <div className="absolute inset-0 bg-gradient-to-t from-[#020617]/80 via-transparent to-transparent z-10" />
              <Image
                src="/images/hero.jpg"
                alt="Sherzodbek Usmonjonov"
                fill
                className="object-cover object-top"
              />
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
            { label: 'Years Experience', value: '2+' },
            { label: 'Projects Built', value: '10+' },
            { label: 'Technologies', value: '15+' },
            { label: 'Lighthouse Score', value: '95+' },
          ].map((stat) => (
            <div
              key={stat.label}
              className="text-center p-6 rounded-2xl border border-white/10 bg-[#0a1628] hover:border-[#38bdf8]/30 transition-colors"
            >
              <p className="text-3xl font-black text-[#38bdf8] mb-1">{stat.value}</p>
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
          <h2 className="text-2xl font-black text-white mb-8">Technical Skills</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {skills.map((group) => (
              <div key={group.category} className="p-6 rounded-2xl border border-white/10 bg-[#0a1628]">
                <h3 className="text-sm font-bold text-[#38bdf8] uppercase tracking-wider mb-4">{group.category}</h3>
                <div className="flex flex-wrap gap-2">
                  {group.items.map((item) => (
                    <span
                      key={item}
                      className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white/5 text-slate-300 border border-white/5"
                    >
                      {item}
                    </span>
                  ))}
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
                <div className="text-3xl mb-4">{service.icon}</div>
                <h3 className="text-base font-bold text-white group-hover:text-[#38bdf8] transition-colors mb-3">
                  {service.title}
                </h3>
                <p className="text-sm text-slate-400 leading-relaxed">{service.desc}</p>
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
          <h2 className="text-3xl font-black text-white mb-3">Let&apos;s Work Together</h2>
          <p className="text-slate-400 mb-8 max-w-md mx-auto">
            Have a project in mind? I&apos;m available for freelance work and open to full-time opportunities.
          </p>
          <Link
            href="/contact"
            className="inline-flex items-center gap-2 px-8 py-4 bg-[#38bdf8] text-[#020617] font-bold rounded-xl hover:bg-sky-300 transition-all hover:shadow-lg hover:shadow-sky-400/25"
          >
            Get In Touch
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
          </Link>
        </motion.div>
      </div>
    </div>
  )
}

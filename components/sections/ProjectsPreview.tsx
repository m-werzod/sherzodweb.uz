'use client'
import { motion } from 'framer-motion'
import Link from 'next/link'
import ProjectCard from '@/components/ui/ProjectCard'
import { useLanguage } from '@/lib/i18n/LanguageContext'

export default function ProjectsPreview() {
  const { ui, projects } = useLanguage()
  return (
    <section className="py-24 px-6">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-14"
        >
          <p className="text-xs text-[#38bdf8] font-semibold tracking-[0.25em] uppercase mb-3">{ui.projectsPreview.eyebrow}</p>
          <h2 className="text-3xl md:text-4xl font-black text-white mb-4">
            {ui.projectsPreview.heading} <span className="text-[#38bdf8]">{ui.projectsPreview.headingHighlight}</span>
          </h2>
          <p className="text-slate-400 max-w-xl mx-auto text-sm leading-relaxed">
            {ui.projectsPreview.subtitle}
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          {projects.homeHighlights.map((project, i) => (
            <ProjectCard key={project.title} project={project} index={i} />
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="text-center"
        >
          <Link
            href="/projects"
            className="inline-flex items-center gap-2 px-8 py-4 border border-white/15 text-white font-semibold rounded-xl hover:border-[#38bdf8]/50 hover:bg-[#38bdf8]/5 hover:text-[#38bdf8] transition-all duration-200 group"
          >
            {ui.projectsPreview.viewAll}
            <svg className="w-4 h-4 group-hover:translate-x-1 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
          </Link>
        </motion.div>
      </div>
    </section>
  )
}

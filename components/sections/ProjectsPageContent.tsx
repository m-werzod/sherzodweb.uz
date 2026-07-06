'use client'
import { motion } from 'framer-motion'
import ProjectCard from '@/components/ui/ProjectCard'
import Link from 'next/link'
import type { CategoryKey } from '@/lib/resumeData'
import { useLanguage } from '@/lib/i18n/LanguageContext'
import { formatTemplate } from '@/lib/i18n/format'

export interface ProjectsPageContentProps {
  /** When set, renders the category-flavored heading/subtitle/contact link for that specialization. */
  category?: CategoryKey
}

export default function ProjectsPageContent({ category }: ProjectsPageContentProps) {
  const { ui, categories, projects } = useLanguage()
  const data = category ? categories[category] : null

  const eyebrow = data ? `${data.label} ${ui.projectsPage.eyebrow}` : ui.projectsPage.eyebrow
  const titlePrefix = data ? '' : ui.projectsPage.titlePrefix
  const titleHighlight = data ? `${data.label} ${ui.projectsPage.titleHighlight}` : ui.projectsPage.titleHighlight
  const subtitle = data
    ? formatTemplate(ui.projectsPage.subtitleCategoryTemplate, { role: data.fullTitle.toLowerCase() })
    : ui.projectsPage.subtitleDefault
  const contactHref = category ? `/${category}/contact` : '/contact'

  return (
    <div className="min-h-screen pt-36 pb-24 px-6">
      <div className="max-w-7xl mx-auto">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <p className="text-xs text-[#38bdf8] font-semibold tracking-[0.25em] uppercase mb-3">{eyebrow}</p>
          <h1 className="text-4xl md:text-5xl font-black text-white mb-4">
            {titlePrefix}<span className="text-[#38bdf8]">{titleHighlight}</span>
          </h1>
          <p className="text-slate-400 max-w-xl mx-auto">{subtitle}</p>
        </motion.div>

        {/* ── Featured ── */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="flex items-center gap-3 mb-6"
        >
          <span className="px-3 py-1 text-xs font-bold rounded-full bg-[#38bdf8]/10 text-[#38bdf8] border border-[#38bdf8]/30 uppercase tracking-widest">
            ★ {ui.projectsPage.featured}
          </span>
          <div className="flex-1 h-px bg-white/5" />
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-16">
          {projects.featuredProjects.map((project, i) => (
            <ProjectCard key={project.title} project={project} index={i} />
          ))}
        </div>

        {/* ── More Work ── */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="flex items-center gap-3 mb-6"
        >
          <span className="px-3 py-1 text-xs font-bold rounded-full bg-white/5 text-slate-400 border border-white/10 uppercase tracking-widest">
            {ui.projectsPage.moreWork}
          </span>
          <div className="flex-1 h-px bg-white/5" />
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.moreProjects.map((project, i) => (
            <ProjectCard key={project.title} project={project} index={i} />
          ))}
        </div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="text-center mt-16"
        >
          <Link
            href={contactHref}
            className="inline-flex items-center gap-2 px-8 py-4 bg-[#38bdf8] text-[#020617] font-bold rounded-xl hover:bg-sky-300 transition-all hover:shadow-lg hover:shadow-sky-400/25"
          >
            {ui.projectsPage.cta}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
          </Link>
        </motion.div>
      </div>
    </div>
  )
}

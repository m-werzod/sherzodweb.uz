'use client'
import { motion } from 'framer-motion'
import Link from 'next/link'
import Image from 'next/image'
import { useLanguage } from '@/lib/i18n/LanguageContext'

export interface Project {
  title: string
  description: string
  tags: string[]
  github: string
  demo: string
  gradient: string
  image?: string
  status?: 'live' | 'wip' | 'archived'
  year?: string
}

export default function ProjectCard({ project, index }: { project: Project; index: number }) {
  const { ui } = useLanguage()
  const hasImage   = !!project.image
  const hasDemo    = project.demo && project.demo !== '#'
  const hasGithub  = project.github && project.github !== '#'

  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5, delay: index * 0.08 }}
      whileHover={{ y: -6 }}
      className="group relative flex flex-col rounded-2xl border border-white/10 bg-[#0a1628] overflow-hidden hover:border-[#38bdf8]/40 transition-all duration-300 hover:shadow-2xl hover:shadow-sky-950/60"
    >
      {/* ── Full-card clickable overlay → demo link ── */}
      {hasDemo && (
        <Link
          href={project.demo}
          target="_blank"
          rel="noopener noreferrer"
          className="absolute inset-0 z-10"
          aria-label={`Open ${project.title}`}
        />
      )}

      {/* ── Image / Placeholder ── */}
      {hasImage ? (
        <div className="relative w-full overflow-hidden" style={{ aspectRatio: '16/9' }}>
          <div className="absolute inset-0 bg-gradient-to-t from-[#0a1628] via-[#0a1628]/20 to-transparent z-[1] pointer-events-none" />
          {project.status === 'live' && (
            <div className="absolute top-3 right-3 z-[2] flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/40 backdrop-blur-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">{ui.projectCard.live}</span>
            </div>
          )}
          <Image
            src={project.image!}
            alt={project.title}
            fill
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
            loading="lazy"
            className="object-cover object-top group-hover:scale-105 transition-transform duration-700"
          />
        </div>
      ) : (
        <div className={`relative w-full bg-gradient-to-br ${project.gradient} overflow-hidden`} style={{ aspectRatio: '16/9' }}>
          <div className="absolute inset-0 bg-[#020617]/60" />
          {project.status === 'live' && (
            <div className="absolute top-3 right-3 z-[2] flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/40">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">{ui.projectCard.live}</span>
            </div>
          )}
          <div className="absolute inset-0 flex items-center justify-center opacity-20">
            <div className="w-24 h-24 sm:w-32 sm:h-32 rounded-full border-4 border-white/40" />
            <div className="absolute w-14 h-14 sm:w-20 sm:h-20 rounded-full border-2 border-white/30" />
          </div>
        </div>
      )}

      {!hasImage && <div className={`h-0.5 w-full bg-gradient-to-r ${project.gradient}`} />}

      {/* ── Content ── */}
      <div className="flex flex-col flex-1 p-4 sm:p-5">
        <h3 className="text-base sm:text-lg font-bold text-white group-hover:text-[#38bdf8] transition-colors duration-200 mb-1.5 leading-snug">
          {project.title}
        </h3>

        <p className="text-xs sm:text-sm text-slate-400 leading-relaxed mb-4 flex-1 line-clamp-3">
          {project.description}
        </p>

        {/* Tags */}
        <div className="flex flex-wrap gap-1.5 mb-4">
          {project.tags.map((tag) => (
            <span
              key={tag}
              className="px-2 py-0.5 text-[10px] sm:text-xs font-semibold rounded-md bg-white/5 text-slate-400 border border-white/8 whitespace-nowrap"
            >
              {tag}
            </span>
          ))}
        </div>

        {/* Action buttons — sit above the overlay via z-20 */}
        <div className="relative z-20 flex items-center gap-2 mt-auto">
          {hasGithub && (
            <Link
              href={project.github}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white transition-colors px-3 py-2 rounded-lg border border-white/10 hover:border-white/25 hover:bg-white/5"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="https://img.icons8.com/3d-fluency/94/github.png" alt="GitHub" width={14} height={14} loading="lazy" decoding="async" className="w-3.5 h-3.5 shrink-0" />
              {ui.projectCard.code}
            </Link>
          )}

          {hasDemo && (
            <Link
              href={project.demo}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1.5 text-xs font-semibold text-[#38bdf8] hover:text-sky-200 transition-colors px-3 py-2 rounded-lg border border-[#38bdf8]/30 hover:border-[#38bdf8]/60 bg-[#38bdf8]/5 hover:bg-[#38bdf8]/10"
            >
              <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              {ui.projectCard.liveDemo}
            </Link>
          )}
        </div>
      </div>
    </motion.div>
  )
}

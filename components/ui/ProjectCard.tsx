'use client'
import { motion } from 'framer-motion'
import Link from 'next/link'

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
  const hasImage = !!project.image

  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5, delay: index * 0.08 }}
      whileHover={{ y: -6 }}
      className="group relative flex flex-col rounded-2xl border border-white/10 bg-[#0a1628] overflow-hidden hover:border-[#38bdf8]/40 transition-all duration-300 hover:shadow-2xl hover:shadow-sky-950/60"
    >
      {/* ── Image / Placeholder ── */}
      {hasImage ? (
        <div className="relative w-full overflow-hidden" style={{ aspectRatio: '16/9' }}>
          {/* Gradient overlay on image */}
          <div className="absolute inset-0 bg-gradient-to-t from-[#0a1628] via-[#0a1628]/20 to-transparent z-10 pointer-events-none" />
          {/* Status badge */}
          {project.status === 'live' && (
            <div className="absolute top-3 right-3 z-20 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/40 backdrop-blur-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">Live</span>
            </div>
          )}
          <img
            src={project.image}
            alt={project.title}
            className="w-full h-full object-cover object-top group-hover:scale-105 transition-transform duration-700"
          />
        </div>
      ) : (
        /* Colourful gradient placeholder for cards without a screenshot */
        <div className={`relative w-full bg-gradient-to-br ${project.gradient} overflow-hidden`} style={{ aspectRatio: '16/9' }}>
          <div className="absolute inset-0 bg-[#020617]/60" />
          {project.status === 'live' && (
            <div className="absolute top-3 right-3 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/40">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">Live</span>
            </div>
          )}
          {/* Abstract pattern */}
          <div className="absolute inset-0 flex items-center justify-center opacity-20">
            <div className="w-24 h-24 sm:w-32 sm:h-32 rounded-full border-4 border-white/40" />
            <div className="absolute w-14 h-14 sm:w-20 sm:h-20 rounded-full border-2 border-white/30" />
          </div>
          {/* Year */}
          {project.year && (
            <span className="absolute bottom-3 left-3 text-xs font-semibold text-white/40">{project.year}</span>
          )}
        </div>
      )}

      {/* ── Colour bar (only for no-image cards) ── */}
      {!hasImage && <div className={`h-0.5 w-full bg-gradient-to-r ${project.gradient}`} />}

      {/* ── Content ── */}
      <div className="flex flex-col flex-1 p-4 sm:p-5">
        {/* Year badge (image cards) */}
        {hasImage && project.year && (
          <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-1">{project.year}</span>
        )}

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

        {/* Links */}
        <div className="flex items-center gap-2 mt-auto">
          <Link
            href={project.github}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white transition-colors px-3 py-2 rounded-lg border border-white/10 hover:border-white/25 hover:bg-white/5 flex-1 justify-center sm:flex-none sm:justify-start"
          >
            <img src="https://img.icons8.com/3d-fluency/94/github.png" alt="GitHub" className="w-3.5 h-3.5 shrink-0" />
            Code
          </Link>

          {project.demo !== '#' && (
            <Link
              href={project.demo}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs font-semibold text-[#38bdf8] hover:text-sky-200 transition-colors px-3 py-2 rounded-lg border border-[#38bdf8]/30 hover:border-[#38bdf8]/60 bg-[#38bdf8]/5 hover:bg-[#38bdf8]/10 flex-1 justify-center sm:flex-none sm:justify-start"
            >
              <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              Live Demo
            </Link>
          )}

          {/* External arrow for image cards */}
          {hasImage && project.demo !== '#' && (
            <Link
              href={project.demo}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto w-8 h-8 flex items-center justify-center rounded-lg border border-white/10 hover:border-[#38bdf8]/40 hover:bg-[#38bdf8]/5 transition-all text-slate-500 hover:text-[#38bdf8]"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6m0 0v6m0-6L10 14" />
              </svg>
            </Link>
          )}
        </div>
      </div>
    </motion.div>
  )
}

'use client'
import { motion } from 'framer-motion'
import Link from 'next/link'

interface Project {
  title: string
  description: string
  tags: string[]
  github: string
  demo: string
  gradient: string
}

export default function ProjectCard({ project, index }: { project: Project; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5, delay: index * 0.1 }}
      whileHover={{ y: -8, scale: 1.02 }}
      className="group relative rounded-2xl border border-white/10 bg-[#0a1628] overflow-hidden hover:border-[#38bdf8]/30 transition-all duration-300 hover:shadow-xl hover:shadow-sky-950/50"
    >
      {/* Top gradient bar */}
      <div className={`h-1.5 w-full bg-gradient-to-r ${project.gradient}`} />

      {/* Glow on hover */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none bg-gradient-to-br from-sky-500/5 to-transparent" />

      <div className="p-6">
        {/* Title */}
        <h3 className="text-lg font-bold text-white group-hover:text-[#38bdf8] transition-colors duration-200 mb-2">
          {project.title}
        </h3>

        {/* Description */}
        <p className="text-sm text-slate-400 leading-relaxed mb-5 line-clamp-3">
          {project.description}
        </p>

        {/* Tags */}
        <div className="flex flex-wrap gap-2 mb-6">
          {project.tags.map((tag) => (
            <span
              key={tag}
              className="px-2.5 py-1 text-xs font-medium rounded-md bg-white/5 text-slate-400 border border-white/5"
            >
              {tag}
            </span>
          ))}
        </div>

        {/* Links */}
        <div className="flex items-center gap-3">
          <Link
            href={project.github}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-white transition-colors px-3 py-2 rounded-lg border border-white/10 hover:border-white/20"
          >
            <img
              src="https://img.icons8.com/3d-fluency/94/github.png"
              alt="GitHub"
              className="w-4 h-4"
            />
            Code
          </Link>
          {project.demo !== '#' && (
            <Link
              href={project.demo}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-xs font-semibold text-[#38bdf8] hover:text-sky-300 transition-colors px-3 py-2 rounded-lg border border-[#38bdf8]/30 hover:border-[#38bdf8]/60 bg-[#38bdf8]/5"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                />
              </svg>
              Live Demo
            </Link>
          )}
        </div>
      </div>
    </motion.div>
  )
}

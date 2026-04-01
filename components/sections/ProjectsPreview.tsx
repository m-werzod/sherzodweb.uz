'use client'
import { motion } from 'framer-motion'
import Link from 'next/link'
import ProjectCard from '@/components/ui/ProjectCard'

const projects = [
  {
    title: 'E-Commerce Platform',
    description:
      'A full-stack e-commerce solution with product catalog, cart, Stripe payments, user authentication, and an admin dashboard. Built for performance and scalability.',
    tags: ['Next.js 14', 'TypeScript', 'Tailwind', 'Stripe', 'Prisma'],
    github: 'https://github.com/m-werzod',
    demo: '#',
    gradient: 'from-sky-500 to-blue-600',
  },
  {
    title: 'Portfolio v1',
    description:
      'First iteration personal portfolio showcasing creative animations, custom cursor effects, and GSAP scroll-triggered transitions with a unique design identity.',
    tags: ['React', 'GSAP', 'CSS3', 'Vite'],
    github: 'https://github.com/m-werzod',
    demo: '#',
    gradient: 'from-purple-500 to-pink-600',
  },
  {
    title: 'Task Manager Pro',
    description:
      'A Trello-inspired drag-and-drop kanban board with real-time collaboration, task assignments, deadlines, and Firebase sync across devices.',
    tags: ['React', 'DnD Kit', 'Firebase', 'Tailwind'],
    github: 'https://github.com/m-werzod',
    demo: '#',
    gradient: 'from-emerald-500 to-teal-600',
  },
]

export default function ProjectsPreview() {
  return (
    <section className="py-24 px-6">
      <div className="max-w-7xl mx-auto">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-14"
        >
          <p className="text-xs text-[#38bdf8] font-semibold tracking-[0.25em] uppercase mb-3">Work</p>
          <h2 className="text-3xl md:text-4xl font-black text-white mb-4">
            Featured <span className="text-[#38bdf8]">Projects</span>
          </h2>
          <p className="text-slate-400 max-w-xl mx-auto text-sm leading-relaxed">
            A selection of projects that showcase my skills in frontend development, motion design, and product thinking.
          </p>
        </motion.div>

        {/* Project cards grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
          {projects.map((project, i) => (
            <ProjectCard key={project.title} project={project} index={i} />
          ))}
        </div>

        {/* View All CTA */}
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
            View All Projects
            <svg
              className="w-4 h-4 group-hover:translate-x-1 transition-transform duration-200"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
          </Link>
        </motion.div>
      </div>
    </section>
  )
}

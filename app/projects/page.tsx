'use client'
import { motion } from 'framer-motion'
import ProjectCard, { Project } from '@/components/ui/ProjectCard'
import Link from 'next/link'

const projects: Project[] = [
  {
    title: 'E-Commerce Platform',
    description:
      'Full-stack e-commerce app with product catalog, admin panel, search & filter, cart, user authentication, and responsive design across desktop & mobile.',
    tags: ['React', 'TypeScript', 'Tailwind CSS', 'Firebase', 'Vite'],
    github: 'https://github.com/m-werzod',
    demo: 'https://e-commerce-with-registration.vercel.app/',
    gradient: 'from-sky-500 to-blue-600',
    status: 'live',
    year: '2024',
  },
  {
    title: 'Portfolio v1',
    description:
      'First iteration personal portfolio with creative animations, smooth scroll transitions, and a unique dark-mode design identity built from scratch.',
    tags: ['React', 'TypeScript', 'Tailwind CSS', 'Framer Motion'],
    github: 'https://github.com/m-werzod',
    demo: '#',
    gradient: 'from-purple-500 to-pink-600',
  },
  {
    title: 'Task Manager Pro',
    description:
      'Trello-inspired drag-and-drop kanban board with task assignments, priorities, deadlines, and real-time sync across devices.',
    tags: ['React', 'TypeScript', 'DnD Kit', 'Firebase'],
    github: 'https://github.com/m-werzod',
    demo: '#',
    gradient: 'from-emerald-500 to-teal-600',
  },
  {
    title: 'Weather Dashboard',
    description:
      'Real-time weather app with 7-day forecasts, animated data visualizations, auto location detection, and interactive charts.',
    tags: ['Next.js', 'TypeScript', 'Chart.js', 'OpenWeather API'],
    github: 'https://github.com/m-werzod',
    demo: '#',
    gradient: 'from-orange-500 to-amber-600',
  },
  {
    title: 'Chat Application',
    description:
      'Real-time chat with WebSocket support, multiple rooms, file sharing, read receipts, typing indicators, and smooth message animations.',
    tags: ['React', 'Socket.io', 'Node.js', 'Express'],
    github: 'https://github.com/m-werzod',
    demo: '#',
    gradient: 'from-rose-500 to-red-600',
  },
  {
    title: 'UI Component Library',
    description:
      '30+ reusable React components with full TypeScript types, dark-mode support, Storybook docs, and zero external UI dependencies.',
    tags: ['React', 'TypeScript', 'Storybook', 'Rollup'],
    github: 'https://github.com/m-werzod',
    demo: '#',
    gradient: 'from-violet-500 to-indigo-600',
  },
]

export default function ProjectsPage() {
  return (
    <div className="min-h-screen pt-28 pb-24 px-6">
      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <p className="text-xs text-[#38bdf8] font-semibold tracking-[0.25em] uppercase mb-3">Portfolio</p>
          <h1 className="text-4xl md:text-5xl font-black text-white mb-4">
            Featured <span className="text-[#38bdf8]">Projects</span>
          </h1>
          <p className="text-slate-400 max-w-xl mx-auto">
            A curated selection of projects showcasing my expertise in frontend development, motion design, and full-stack solutions.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((project, i) => (
            <ProjectCard key={project.title} project={project} index={i} />
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="text-center mt-16"
        >
          <Link
            href="/contact"
            className="inline-flex items-center gap-2 px-8 py-4 bg-[#38bdf8] text-[#020617] font-bold rounded-xl hover:bg-sky-300 transition-all hover:shadow-lg hover:shadow-sky-400/25"
          >
            Start a Project Together
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
          </Link>
        </motion.div>
      </div>
    </div>
  )
}

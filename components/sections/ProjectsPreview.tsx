'use client'
import { motion } from 'framer-motion'
import Link from 'next/link'
import ProjectCard, { Project } from '@/components/ui/ProjectCard'

const projects: Project[] = [
  {
    title: 'E-Commerce Platform',
    description:
      'Full-featured online store with product catalog, admin dashboard, search & filter, shopping cart, user authentication, and fully responsive UI across all devices.',
    tags: ['React', 'TypeScript', 'Tailwind CSS', 'Vite', 'Redux Toolkit', 'Axios', 'React Query', 'React Hot Toast'],
    github: 'https://github.com/m-werzod',
    demo: 'https://e-commerce-with-registration.vercel.app/',
    gradient: 'from-sky-500 to-blue-600',
    image: '/images/projects/ecommerce.webp',
    status: 'live',
    year: '2024',
  },
  {
    title: 'Restaurant Website',
    description:
      'Modern restaurant landing page with interactive menu, reservation system, animated sections, photo gallery, and mobile-first responsive design.',
    tags: ['Next.js', 'TypeScript', 'Tailwind CSS', 'shadcn/ui', 'Lucide React', 'React Cookie'],
    github: 'https://github.com/m-werzod',
    demo: 'https://restaurant-ten-self.vercel.app/',
    gradient: 'from-orange-500 to-red-600',
    image: '/images/projects/restaurant.webp',
    status: 'live',
    year: '2024',
  },
  {
    title: 'Edu CRM / ERP System',
    description:
      'Educational management platform with student tracking, course management, attendance, grade reports, and a clean admin dashboard for institutions.',
    tags: ['React', 'TypeScript', 'Tailwind CSS', 'Ant Design', 'Axios', 'React Query', 'React Hot Toast', 'React Cookie'],
    github: 'https://github.com/m-werzod',
    demo: 'https://edu-crm-erp.vercel.app/',
    gradient: 'from-emerald-500 to-teal-600',
    image: '/images/projects/educrm.webp',
    status: 'live',
  },
  {
    title: 'Business Finance Manager',
    description:
      'Full-stack business finance management app with income & expense tracking, budget planning, transaction history, category breakdowns, and interactive dashboard analytics.',
    tags: ['React', 'TypeScript', 'Next.js', 'Node.js', 'Tailwind CSS', 'Recharts', 'PostgreSQL', 'JWT'],
    github: 'https://github.com/m-werzod',
    demo: 'https://finance-manager-theta-six.vercel.app/',
    gradient: 'from-green-500 to-emerald-600',
    image: '/images/projects/finance.jpg',
    status: 'live',
  },
]

export default function ProjectsPreview() {
  return (
    <section className="py-24 px-6">
      <div className="max-w-7xl mx-auto">
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
            A selection of real-world projects — e-commerce, CRM systems, restaurants, and more.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          {projects.map((project, i) => (
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
            View All Projects
            <svg className="w-4 h-4 group-hover:translate-x-1 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
          </Link>
        </motion.div>
      </div>
    </section>
  )
}

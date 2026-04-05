'use client'
import { motion } from 'framer-motion'
import ProjectCard, { Project } from '@/components/ui/ProjectCard'
import Link from 'next/link'

const featured: Project[] = [
  {
    title: 'E-Commerce Platform',
    description:
      'Full-featured online store with product catalog, admin dashboard, search & filter, shopping cart, user authentication, and fully responsive UI across all devices.',
    tags: ['React', 'TypeScript', 'Tailwind CSS', 'Vite', 'Redux Toolkit', 'Axios', 'React Query', 'React Hot Toast'],
    github: 'https://github.com/m-werzod',
    demo: 'https://e-commerce-with-registration.vercel.app/',
    gradient: 'from-sky-500 to-blue-600',
    image: '/images/projects/ecommerce.png',
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
    image: '/images/projects/restaurant.png',
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
    image: '/images/projects/educrm.png',
    status: 'live',
    year: '2024',
  },
]

const more: Project[] = [
  {
    title: 'Toshkent Baliqchi',
    description:
      'Fish restaurant landing page with animated menu sections, location map, contact form, and a fresh nautical-themed UI optimised for mobile.',
    tags: ['React', 'Tailwind CSS', 'JavaScript'],
    github: 'https://github.com/m-werzod',
    demo: 'https://toshkent-baliqchi.vercel.app/',
    gradient: 'from-cyan-500 to-blue-500',
    status: 'live',
    year: '2024',
  },
  {
    title: 'Nexora Labs — Company Site',
    description:
      'Corporate website for a tech company featuring service showcase, team section, animated hero, and a modern dark design system.',
    tags: ['React', 'Next.js', 'Tailwind CSS'],
    github: 'https://github.com/m-werzod/Nexora-labs-company',
    demo: '#',
    gradient: 'from-violet-500 to-purple-600',
    year: '2024',
  },
  {
    title: 'iPhone Store UZ',
    description:
      'Apple product e-commerce storefront with product listing, category filter, cart, and a pixel-perfect Apple-inspired UI for the Uzbekistan market.',
    tags: ['React', 'TypeScript', 'Tailwind CSS', 'Vite'],
    github: 'https://github.com/m-werzod/IPHONE-STORE.UZ',
    demo: '#',
    gradient: 'from-slate-400 to-slate-600',
    year: '2024',
  },
  {
    title: 'Fitness Time Gym',
    description:
      'Gym landing page with pricing plans, class schedule, trainer profiles, animated stats counter, and a bold high-energy design.',
    tags: ['React', 'Tailwind CSS', 'JavaScript'],
    github: 'https://github.com/m-werzod',
    demo: 'https://fitness-time-gym.vercel.app/',
    gradient: 'from-yellow-500 to-orange-500',
    status: 'live',
    year: '2024',
  },
  {
    title: 'Parfume Market',
    description:
      'Luxury perfume shop with product cards, scent-category filtering, wishlist, cart, and an elegant glassmorphism UI.',
    tags: ['React', 'TypeScript', 'Tailwind CSS', 'Vite'],
    github: 'https://github.com/m-werzod',
    demo: 'https://parfume-market-nu.vercel.app/',
    gradient: 'from-pink-500 to-rose-600',
    status: 'live',
    year: '2024',
  },
  {
    title: 'Barakah Restaurant',
    description:
      'Full restaurant website with animated menu, online table reservation, gallery, customer reviews section, and smooth page transitions.',
    tags: ['React', 'Tailwind CSS', 'JavaScript'],
    github: 'https://github.com/m-werzod',
    demo: 'https://barakahresturant.vercel.app/',
    gradient: 'from-amber-500 to-yellow-600',
    status: 'live',
    year: '2025',
  },
  {
    title: 'Sherzoddev Portfolio',
    description:
      'This portfolio — built with Next.js 15, animated with Framer Motion, 3D visuals via React Three Fiber, and a full-stack contact system with Telegram & Gmail.',
    tags: ['Next.js', 'TypeScript', 'Three.js', 'Tailwind CSS', 'React Three Fiber'],
    github: 'https://github.com/m-werzod',
    demo: 'https://sherzoddev.com',
    gradient: 'from-[#38bdf8] to-indigo-500',
    status: 'live',
    year: '2025',
  },
]

export default function ProjectsPage() {
  return (
    <div className="min-h-screen pt-28 pb-24 px-6">
      <div className="max-w-7xl mx-auto">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <p className="text-xs text-[#38bdf8] font-semibold tracking-[0.25em] uppercase mb-3">Portfolio</p>
          <h1 className="text-4xl md:text-5xl font-black text-white mb-4">
            All <span className="text-[#38bdf8]">Projects</span>
          </h1>
          <p className="text-slate-400 max-w-xl mx-auto">
            10 real-world projects — from e-commerce and CRM systems to restaurant brands and 3D portfolios.
          </p>
        </motion.div>

        {/* ── Featured Top 3 ── */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="flex items-center gap-3 mb-6"
        >
          <span className="px-3 py-1 text-xs font-bold rounded-full bg-[#38bdf8]/10 text-[#38bdf8] border border-[#38bdf8]/30 uppercase tracking-widest">
            ★ Featured
          </span>
          <div className="flex-1 h-px bg-white/5" />
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-16">
          {featured.map((project, i) => (
            <ProjectCard key={project.title} project={project} index={i} />
          ))}
        </div>

        {/* ── More Projects ── */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="flex items-center gap-3 mb-6"
        >
          <span className="px-3 py-1 text-xs font-bold rounded-full bg-white/5 text-slate-400 border border-white/10 uppercase tracking-widest">
            More Work
          </span>
          <div className="flex-1 h-px bg-white/5" />
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {more.map((project, i) => (
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

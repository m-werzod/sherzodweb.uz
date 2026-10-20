import type { Project } from '@/components/ui/ProjectCard'

export type { Project }

/** Flagship platforms — architected end-to-end, shown first everywhere. */
export const flagshipProjects: Project[] = [
  {
    title: 'Era AI Platform',
    description:
      'Full-stack AI aggregation platform connecting 40+ third-party AI tools behind one unified interface — architected and owned solo end-to-end, from prompt-engineering pipelines to the PostgreSQL data layer.',
    tags: ['React 19', 'Next.js', 'TypeScript', 'Node.js', 'PostgreSQL', 'Prisma', 'OpenAI API', 'Claude API', 'Gemini API'],
    github: 'https://github.com/m-werzod',
    demo: 'https://era2-frontend.vercel.app/',
    gradient: 'from-indigo-500 via-purple-500 to-fuchsia-600',
    image: '/images/projects/era-ai.png',
    status: 'live',
    year: '2026',
  },
  {
    title: 'Labour Migration Agency Platform',
    description:
      'Production platform for a private employment agency — candidate intake forms, vacancy listings, and a complete admin management panel, backed by a relational PostgreSQL schema and role-based access control.',
    tags: ['React', 'Next.js', 'TypeScript', 'Node.js', 'PostgreSQL', 'REST API', 'RBAC'],
    github: 'https://github.com/m-werzod',
    demo: 'https://labour-agency.vercel.app/',
    gradient: 'from-sky-600 via-blue-600 to-cyan-500',
    image: '/images/projects/labour-agency.png',
    status: 'live',
    year: '2026',
  },
]

/** Best pick from the rest of the catalogue, promoted to the homepage alongside the flagships. */
export const homeHighlightPick: Project = {
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
}

/** Shown on the homepage preview — the two flagship platforms plus the strongest existing project. */
export const homeHighlights: Project[] = [...flagshipProjects, homeHighlightPick]

/** Shown in the "Featured" section of the full /projects page — every featured project. */
export const featuredProjects: Project[] = [
  ...flagshipProjects,
  {
    title: 'AI Automation Platform',
    description:
      'Company automation platform uniting plugins for Gmail, Telegram, Instagram and more — full auth flow, a built-in CRM, and AI agents that run multi-channel workflows end to end.',
    tags: ['Next.js', 'TypeScript', 'AI Agents', 'CRM', 'Telegram API', 'Instagram API', 'Gmail API'],
    github: 'https://github.com/m-werzod',
    demo: 'https://telegram-instagram-automation.vercel.app/',
    gradient: 'from-violet-600 via-purple-500 to-fuchsia-500',
    image: '/images/projects/automation-platform.jpg',
    status: 'live',
    year: '2026',
  },
  {
    title: 'Instagram AI Leads — Marketing SaaS',
    description:
      'Instagram automation SaaS for private organizations — Meta-integrated ad payments, comment & DM automation, 10+ built-in AI agents, AI video editing, AI post scheduling, boosts and AI lead buttons.',
    tags: ['Next.js', 'TypeScript', 'Meta API', 'Instagram API', 'AI Agents', 'SaaS', 'Payments'],
    github: 'https://github.com/m-werzod',
    demo: 'https://instagramaileads.vercel.app/',
    gradient: 'from-rose-500 via-pink-500 to-orange-400',
    image: '/images/projects/instagram-ai-leads.jpg',
    status: 'live',
    year: '2026',
  },
  {
    title: 'Tashkent 3D Apartment Platform',
    description:
      'Interactive 3D real-estate platform for selling apartments in Tashkent buildings — explore blocks and floors in 3D, browse unit details, and go from visualization straight to a purchase inquiry.',
    tags: ['Next.js', 'TypeScript', 'Three.js', '3D', 'Real Estate'],
    github: 'https://github.com/m-werzod',
    demo: 'https://tashkent-apartment-3d-platform.vercel.app/',
    gradient: 'from-teal-500 via-cyan-500 to-sky-500',
    image: '/images/projects/tashkent-3d.jpg',
    status: 'live',
    year: '2026',
  },
  homeHighlightPick,
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
  {
    title: 'Turon Avtomaktab — Driving School Platform',
    description:
      'Production website for a 7-branch driving school in Namangan — license category catalogue, dynamic course pricing, branch locator, deposit-based student registration, results & photo gallery, fully localized in Uzbek, Russian and English.',
    tags: ['Next.js', 'TypeScript', 'Tailwind CSS', 'i18n'],
    github: 'https://github.com/m-werzod',
    demo: 'https://www.avtomaktabturon.uz/',
    gradient: 'from-slate-600 to-orange-500',
    image: '/images/projects/turon-avtomaktab.jpg',
    status: 'live',
  },
]

/** The rest of the catalogue — shown under "More Work" on the full /projects page. */
export const moreProjects: Project[] = [
  {
    title: 'Pera Hotel Tashkent',
    description:
      'Hotel website for Pera Hotel in Tashkent — room showcase, amenities, booking inquiry, and an elegant mobile-first presentation.',
    tags: ['Next.js', 'TypeScript', 'Tailwind CSS'],
    github: 'https://github.com/m-werzod',
    demo: 'https://pera-hotel-tashkent.vercel.app/',
    gradient: 'from-amber-500 to-orange-600',
    image: '/images/projects/pera-hotel.jpg',
    status: 'live',
    year: '2026',
  },
  {
    title: 'Toshkent Baliqchi',
    description:
      'Fish restaurant landing page with animated menu sections, location map, contact form, and a fresh nautical-themed UI optimised for mobile.',
    tags: ['React', 'Tailwind CSS', 'JavaScript'],
    github: 'https://github.com/m-werzod',
    demo: 'https://toshkent-baliqchi.vercel.app/',
    gradient: 'from-cyan-500 to-blue-500',
    image: '/images/projects/baliqchi.jpg',
    status: 'live',
  },
  {
    title: 'Nexora Labs — Company Site',
    description:
      'Corporate website for a tech company featuring service showcase, team section, animated hero, and a modern dark design system.',
    tags: ['React', 'Next.js', 'Tailwind CSS'],
    github: 'https://github.com/m-werzod/Nexora-labs-company',
    demo: 'https://github.com/m-werzod/Nexora-labs-company',
    gradient: 'from-violet-500 to-purple-600',
    image: '/images/projects/nexora.jpg',
  },
  {
    title: 'iPhone Store UZ',
    description:
      'Apple product e-commerce storefront with product listing, category filter, cart, and a pixel-perfect Apple-inspired UI for the Uzbekistan market.',
    tags: ['React', 'TypeScript', 'Tailwind CSS', 'Vite'],
    github: 'https://github.com/m-werzod/IPHONE-STORE.UZ',
    demo: 'https://github.com/m-werzod/IPHONE-STORE.UZ',
    gradient: 'from-slate-400 to-slate-600',
    image: '/images/projects/iphone-store.jpg',
  },
  {
    title: 'Fitness Time Gym',
    description:
      'Gym landing page with pricing plans, class schedule, trainer profiles, animated stats counter, and a bold high-energy design.',
    tags: ['React', 'Tailwind CSS', 'JavaScript'],
    github: 'https://github.com/m-werzod',
    demo: 'https://fitness-time-gym.vercel.app/',
    gradient: 'from-yellow-500 to-orange-500',
    image: '/images/projects/fitness.jpg',
    status: 'live',
  },
  {
    title: 'Parfume Market',
    description:
      'Luxury perfume shop with product cards, scent-category filtering, wishlist, cart, and an elegant glassmorphism UI.',
    tags: ['React', 'TypeScript', 'Tailwind CSS', 'Vite'],
    github: 'https://github.com/m-werzod',
    demo: 'https://parfume-market-nu.vercel.app/',
    gradient: 'from-pink-500 to-rose-600',
    image: '/images/projects/parfume.jpg',
    status: 'live',
  },
  {
    title: 'Barakah Restaurant',
    description:
      'Full restaurant website with animated menu, online table reservation, gallery, customer reviews section, and smooth page transitions.',
    tags: ['React', 'Tailwind CSS', 'JavaScript'],
    github: 'https://github.com/m-werzod',
    demo: 'https://barakahresturant.vercel.app/',
    gradient: 'from-amber-500 to-yellow-600',
    image: '/images/projects/barakah.jpg',
    status: 'live',
  },
  {
    title: 'Sherzoddev Portfolio',
    description:
      'This portfolio — built with Next.js 15, animated with Framer Motion, 3D visuals via React Three Fiber, and a full-stack contact system with Telegram & Gmail.',
    tags: ['Next.js', 'TypeScript', 'Three.js', 'Tailwind CSS', 'React Three Fiber'],
    github: 'https://github.com/m-werzod',
    demo: 'https://sherzoddev.com',
    gradient: 'from-[#38bdf8] to-indigo-500',
    image: '/images/projects/portfolio.jpg',
    status: 'live',
  },
]

export const allProjects: Project[] = [...featuredProjects, ...moreProjects]

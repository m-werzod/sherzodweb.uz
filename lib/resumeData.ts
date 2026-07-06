export type CategoryKey = 'full-stack' | 'frontend' | 'ai-specialist' | 'qa-tester'

export interface Language {
  name: string
  flag: string
  level: string
  fill: number
}

export interface ExperienceEntry {
  role: string
  company: string
  companyHref?: string
  period: string
  bullets: string[]
}

export interface CompetencyGroup {
  category: string
  items: string[]
}

export interface HeroStat {
  value: string
  label: string
}

export interface CategoryData {
  slug: CategoryKey
  label: string
  fullTitle: string
  tagline: string
  summary: string[]
  heroStats: HeroStat[]
  competencies: CompetencyGroup[]
  howIWork?: { title: string; bullets: string[] }
  experience: ExperienceEntry[]
  education: string[]
  certifications: string[]
  languages: Language[]
  accent: 'sky' | 'violet' | 'fuchsia' | 'amber'
  icon: 'code' | 'layout' | 'sparkles' | 'shield-check'
}

const LANGUAGES_STANDARD: Language[] = [
  { name: 'Uzbek', flag: 'https://flagcdn.com/w80/uz.png', level: 'Native', fill: 100 },
  { name: 'English', flag: 'https://flagcdn.com/w80/gb.png', level: 'Fluent — C1, IELTS Band 7+', fill: 90 },
  { name: 'Russian', flag: 'https://flagcdn.com/w80/ru.png', level: 'Conversational', fill: 45 },
]

const EDUCATION_STANDARD = ['Bachelor of Business Management — Tashkent State University of Economics (In Progress)']

export const categories: Record<CategoryKey, CategoryData> = {
  'full-stack': {
    slug: 'full-stack',
    label: 'Full Stack',
    fullTitle: 'Full-Stack Developer',
    tagline: 'Node.js · TypeScript · React 19 · Next.js · Python · .NET · AI Integration',
    summary: [
      'Full-Stack Developer building production web applications end to end — React 19 / Next.js frontends on Node.js, Express, and PostgreSQL/Prisma backends — internationally certified as a Frontend Engineer Expert by micro1 (United States).',
      'Proven, measurable results across five live platforms (enterprise ERP, e-commerce, fintech SaaS, and AI products): 98/100 Lighthouse scores, 50% fewer redundant re-renders, and 40% lower server query volume. Currently architecting Era AI, a full-stack platform integrating 40+ AI tools and APIs behind one unified interface.',
      'Backend range extends to Python (Django, scripting & automation) and .NET (C# / ASP.NET Core), with type-safe architecture (generics, Zod) and AI-augmented delivery (Claude Code, Cursor AI) for up to 10x faster shipping.',
    ],
    heroStats: [
      { value: '5+', label: 'Live Platforms Shipped' },
      { value: '40+', label: 'AI APIs Integrated' },
      { value: '98/100', label: 'Lighthouse Score' },
      { value: '10x', label: 'Faster with AI-Augmented Delivery' },
    ],
    competencies: [
      { category: 'Languages', items: ['TypeScript (Advanced Generics, Mapped Types, Zod)', 'JavaScript (ES6+/ESNext)', 'Python', 'SQL', 'C# (Working Knowledge)'] },
      { category: 'Backend & APIs', items: ['Node.js', 'Express', 'REST & GraphQL API Design', 'PostgreSQL', 'Prisma ORM', 'MongoDB', 'Django (Working Knowledge)', '.NET / ASP.NET Core', 'Clerk / NextAuth / JWT'] },
      { category: 'Frontend Engineering', items: ['React 19', 'Next.js (App Router, SSR, Server Actions)', 'Redux Toolkit', 'TanStack Query v5', 'Tailwind CSS'] },
      { category: 'AI Integration & Automation', items: ['OpenAI / Claude / Gemini APIs', 'Prompt Engineering', 'n8n Workflow Automation', 'Claude Code', 'Cursor AI', 'GitHub Copilot'] },
      { category: 'Testing & Performance', items: ['Vitest', 'Jest', 'Playwright', 'Core Web Vitals', 'Lighthouse Optimization'] },
      { category: 'Architecture & DevOps', items: ['RBAC', 'Monorepo (Turborepo)', 'Git/GitHub', 'CI/CD', 'Vercel', 'Docker (Basics)'] },
    ],
    experience: [
      {
        role: 'Full-Stack Engineer & AI Integration Developer',
        company: 'Era AI Platform',
        companyHref: 'https://era2-frontend.vercel.app/',
        period: '2026 – Present',
        bullets: [
          'Architected and shipped Era AI, a full-stack AI aggregation platform integrating 40+ third-party AI tools and APIs behind a single unified interface built with React 19, Next.js, and TypeScript.',
          'Own the entire stack as sole developer — type-safe frontend, Node.js services, and PostgreSQL/Prisma data layer — supporting continuous feature expansion in production.',
          'Applied prompt engineering to standardize and optimize outputs across multiple LLM providers (OpenAI, Claude, Gemini), improving response consistency for end users.',
          'Built a responsive admin-style management interface for AI tool listings, user interactions, and automated workflows connecting systems end to end.',
        ],
      },
      {
        role: 'AI & LLM Evaluation Contractor',
        company: 'micro1 (United States) — Titan Onyx Program',
        period: '2026 – Present',
        bullets: [
          'Evaluate and calibrate outputs from multiple large language models against strict guideline criteria for a US AI company, contributing directly to model training and quality benchmarks.',
          "Earned micro1's internationally recognized Frontend Engineer Expert certification through independently proctored testing of React, TypeScript, and system-design skills.",
        ],
      },
      {
        role: 'Full-Stack Developer',
        company: 'Labour Migration Agency Platform (Specialist Group)',
        companyHref: 'https://labour-agency.vercel.app/',
        period: '2026',
        bullets: [
          'Delivered a production platform for a private employment agency, covering candidate intake forms, vacancy listings, and a complete admin management panel.',
          'Designed the PostgreSQL schema and REST API layer connecting the Next.js frontend to backend services, ensuring reliable data flow between public-facing forms and the admin dashboard.',
          'Implemented Role-Based Access Control (RBAC) to cleanly separate administrator and applicant-facing functionality within a single deployed system.',
        ],
      },
      {
        role: 'Full-Stack Frontend Engineer',
        company: 'Business Finance Manager (SaaS)',
        period: '2026',
        bullets: [
          'Architected a type-safe business finance SaaS in TypeScript and Next.js with 100% type-safe data flow from Prisma to UI, achieving a 97/100 Lighthouse score.',
          'Engineered a real-time cash-flow analytics dashboard using TanStack Query optimistic updates and automated cache invalidation — reducing perceived load time by 60%.',
          'Developed high-performance data-visualization modules that render smoothly on datasets exceeding 10,000+ financial transactions without UI lag.',
          'Implemented end-to-end Zod schema validation across all financial inputs, eliminating runtime errors throughout the transaction lifecycle.',
        ],
      },
      {
        role: 'Frontend Engineer',
        company: 'Educational CRM & ERP Platform',
        period: '2026',
        bullets: [
          'Reduced development cycles by 35% by building a TypeScript-first reusable component library and translating complex Figma designs into pixel-perfect, responsive UI.',
          'Improved UI responsiveness by 50% through a custom state-management middleware layer that eliminated redundant re-renders at enterprise scale.',
          'Engineered a multi-tier RBAC system across 3+ administrative levels, securing sensitive student data while preserving a seamless, high-speed user experience.',
        ],
      },
      {
        role: 'Frontend Developer',
        company: 'E-Commerce Storefront (Toshkent Baliqchi)',
        period: '2025',
        bullets: [
          'Deployed a high-traffic SSR storefront with Next.js App Router and Tailwind CSS, driving a 25% increase in SEO indexing with sub-second page transitions.',
          'Refactored global state with Redux Toolkit to manage a 500+ SKU inventory with zero-latency asynchronous updates.',
          'Engineered a custom debounced search engine and multi-criteria filtering system, reducing server-side query volume by 40%.',
        ],
      },
    ],
    education: EDUCATION_STANDARD,
    certifications: [
      'Frontend Engineer Expert Certification — micro1 (United States), 2026 — internationally recognized, independently proctored',
      "Frontend Engineering Program — Najot Ta'lim, 2025 – 2026 — Graduated",
      "AI Prompt Engineering (IT-Focused) — Najot Ta'lim, 2026 — Graduated",
    ],
    languages: LANGUAGES_STANDARD,
    accent: 'sky',
    icon: 'code',
  },

  frontend: {
    slug: 'frontend',
    label: 'Frontend',
    fullTitle: 'Frontend Engineer Expert',
    tagline: 'TypeScript · React 19 · Next.js · AI Integration Specialist',
    summary: [
      'TypeScript-expert Frontend Engineer building production-grade React 19 and Next.js applications, internationally certified as a Frontend Engineer Expert by micro1 (United States).',
      'Proven, measurable results across five live platforms — enterprise ERP, e-commerce, fintech SaaS, and AI products: 98/100 Lighthouse scores, 50% fewer redundant re-renders, and 40% lower server query volume. Currently architecting Era AI, a full-stack platform integrating 40+ AI tools and APIs behind one unified interface.',
      'Combines advanced type-safe architecture (generics, mapped types, Zod) with full-stack range (Node.js, PostgreSQL, Prisma) and AI-augmented delivery (Claude Code, Cursor AI) for up to 10x faster shipping.',
    ],
    heroStats: [
      { value: '98/100', label: 'Lighthouse Score' },
      { value: '50%', label: 'Fewer Redundant Re-renders' },
      { value: '40%', label: 'Lower Server Query Volume' },
      { value: '5', label: 'Live Platforms Shipped' },
    ],
    competencies: [
      { category: 'TypeScript & JavaScript', items: ['Advanced Generics', 'Mapped & Utility Types', 'Type-Safe API Contracts', 'Zod Schema Validation', 'ES6+/ESNext', 'Functional Programming'] },
      { category: 'Frontend Engineering', items: ['React 19', 'Next.js (App Router, SSR, Server Actions)', 'Redux Toolkit', 'TanStack Query v5', 'Tailwind CSS', 'HTML5/CSS3', 'WCAG Accessibility'] },
      { category: 'Backend & APIs', items: ['Node.js', 'Express', 'PostgreSQL', 'Prisma ORM', 'REST & GraphQL API Design', 'Clerk / NextAuth'] },
      { category: 'AI Integration & Automation', items: ['OpenAI / Claude / Gemini APIs', 'Prompt Engineering', 'n8n Workflow Automation', 'Claude Code', 'Cursor AI', 'GitHub Copilot'] },
      { category: 'Testing & Performance', items: ['Vitest', 'Jest', 'Playwright', 'Core Web Vitals', 'Dynamic Code Splitting', 'Memoization', 'Web Workers'] },
      { category: 'Architecture & DevOps', items: ['Reusable Component Libraries', 'Atomic Design', 'RBAC', 'Micro-Frontend Patterns', 'Turborepo', 'CI/CD', 'Vercel'] },
    ],
    experience: [
      {
        role: 'Full-Stack Engineer & AI Integration Developer',
        company: 'Era AI Platform',
        companyHref: 'https://era2-frontend.vercel.app/',
        period: '2026 – Present',
        bullets: [
          'Architected and shipped Era AI, a full-stack AI aggregation platform integrating 40+ third-party AI tools and APIs behind a single unified interface built with React 19, Next.js, and TypeScript.',
          'Own the entire stack as sole developer — type-safe frontend, Node.js services, and PostgreSQL/Prisma data layer — supporting continuous feature expansion in production.',
          'Applied prompt engineering to standardize and optimize outputs across multiple LLM providers (OpenAI, Claude, Gemini), improving response consistency for end users.',
          'Built a responsive admin-style management interface for AI tool listings, user interactions, and automated workflows connecting systems end to end.',
        ],
      },
      {
        role: 'AI & LLM Evaluation Contractor',
        company: 'micro1 (United States) — Titan Onyx Program',
        period: '2026 – Present',
        bullets: [
          'Evaluate and calibrate outputs from multiple large language models against strict guideline criteria for a US AI company, contributing directly to model training and quality benchmarks.',
          "Earned micro1's internationally recognized Frontend Engineer Expert certification through independently proctored testing of React, TypeScript, and system-design skills.",
        ],
      },
      {
        role: 'Full-Stack Developer',
        company: 'Labour Migration Agency Platform (Specialist Group)',
        companyHref: 'https://labour-agency.vercel.app/',
        period: '2026',
        bullets: [
          'Delivered a production platform for a private employment agency, covering candidate intake forms, vacancy listings, and a complete admin management panel.',
          'Designed the PostgreSQL schema and REST API layer connecting the Next.js frontend to backend services, ensuring reliable data flow between public-facing forms and the admin dashboard.',
          'Implemented Role-Based Access Control (RBAC) to cleanly separate administrator and applicant-facing functionality within a single deployed system.',
        ],
      },
      {
        role: 'Full-Stack Frontend Engineer',
        company: 'Business Finance Manager (SaaS)',
        period: '2026',
        bullets: [
          'Architected a type-safe business finance SaaS in TypeScript and Next.js with 100% type-safe data flow from Prisma to UI, achieving a 97/100 Lighthouse score.',
          'Engineered a real-time cash-flow analytics dashboard using TanStack Query optimistic updates and automated cache invalidation — reducing perceived load time by 60%.',
          'Developed high-performance data-visualization modules that render smoothly on datasets exceeding 10,000+ financial transactions without UI lag.',
        ],
      },
      {
        role: 'Frontend Engineer',
        company: 'Educational CRM & ERP Platform',
        period: '2026',
        bullets: [
          'Reduced development cycles by 35% by building a TypeScript-first reusable component library and translating complex Figma designs into pixel-perfect, responsive UI.',
          'Improved UI responsiveness by 50% through a custom state-management middleware layer that eliminated redundant re-renders at enterprise scale.',
          'Achieved a 98/100 Lighthouse Performance score via Server-Side Rendering, dynamic code splitting, and CSS/asset optimization.',
        ],
      },
      {
        role: 'Frontend Developer',
        company: 'E-Commerce Storefront (Toshkent Baliqchi)',
        period: '2025',
        bullets: [
          'Deployed a high-traffic SSR storefront with Next.js App Router and Tailwind CSS, driving a 25% increase in SEO indexing with sub-second page transitions across devices.',
          'Refactored global state with Redux Toolkit to manage a 500+ SKU inventory with zero-latency asynchronous updates.',
          'Engineered a custom debounced search engine and multi-criteria filtering system, reducing server-side query volume by 40%.',
        ],
      },
    ],
    education: EDUCATION_STANDARD,
    certifications: [
      'Frontend Engineer Expert Certification — micro1 (United States), 2026 — internationally recognized, independently proctored',
      "Frontend Engineering Program — Najot Ta'lim, 2025 – 2026 — Graduated",
      "AI Prompt Engineering (IT-Focused) — Najot Ta'lim, 2026 — Graduated",
    ],
    languages: LANGUAGES_STANDARD,
    accent: 'violet',
    icon: 'layout',
  },

  'ai-specialist': {
    slug: 'ai-specialist',
    label: 'AI Specialist',
    fullTitle: 'AI Software Engineer',
    tagline: 'Full-Stack Developer · Prompt Engineering Specialist',
    summary: [
      'AI-driven Full-Stack Software Engineer specializing in integrating large language models (OpenAI, Claude, Gemini, Mistral) into production web platforms through prompt engineering and API automation.',
      'Independently architected and deployed Era AI, a full-stack AI aggregation platform connecting 40+ AI tools via API, alongside enterprise-grade React/Next.js/Node.js applications backed by PostgreSQL.',
      'Combines hands-on AI model evaluation experience with a native command of Uzbek (C2) and fluent English (C1, IELTS 7+), positioning as a cross-functional collaborator ready to build AI-powered platforms, admin panels, and automation systems from concept to deployment.',
    ],
    heroStats: [
      { value: '40+', label: 'AI Tools Integrated via API' },
      { value: '4', label: 'LLM Providers Orchestrated' },
      { value: '98/100', label: 'Lighthouse Score' },
      { value: '1', label: 'Solo-Owned AI Platform in Production' },
    ],
    competencies: [
      { category: 'AI & LLM Engineering', items: ['LLM Integration (OpenAI, Claude, Gemini, Mistral)', 'Prompt Engineering', 'AI Workflow Automation', 'AI Chatbot Development'] },
      { category: 'Backend & Automation', items: ['Python (Scripting & Automation)', 'Node.js', 'REST API Design & Integration', 'n8n Workflow Automation'] },
      { category: 'Database', items: ['PostgreSQL', 'MySQL', 'SQL', 'Prisma ORM'] },
      { category: 'Frontend & Admin Systems', items: ['React', 'Next.js', 'TypeScript', 'Admin Panel Development'] },
      { category: 'Version Control & DevOps', items: ['Git', 'GitHub', 'CI/CD Pipelines', 'Vercel Deployment'] },
    ],
    experience: [
      {
        role: 'Full-Stack AI Engineer',
        company: 'Era AI Platform',
        companyHref: 'https://era2-frontend.vercel.app/',
        period: '2026 – Present',
        bullets: [
          'Architected and shipped Era AI, a full-stack AI aggregation platform, measured by 40+ integrated AI tools accessible from a single interface, by building a React 19/Next.js frontend on a Node.js and Python-scripted automation backend.',
          'Orchestrated multi-model LLM integrations (OpenAI, Claude, Gemini, Mistral), measured by seamless model-switching for end users, by designing reusable prompt engineering pipelines and API abstraction layers.',
          'Sustained continuous solo ownership of the platform, measured by ongoing feature releases post-launch, by independently managing the full development lifecycle from architecture to deployment on Vercel.',
        ],
      },
      {
        role: 'AI Trainer & Evaluator',
        company: 'micro1 — Titan Onyx Program (U.S.-based)',
        period: '2026',
        bullets: [
          'Evaluated and calibrated AI model outputs, measured by consistent adherence to scoring guidelines across hundreds of tasks, by conducting structured video/audio annotation, transcription, and AI screener assessments.',
          'Improved model response quality, measured by calibration accuracy against guideline benchmarks, by applying prompt engineering judgment to content moderation and response-quality evaluation workflows.',
          'Operated as an international contractor for a U.S.-based AI training company, gaining direct exposure to enterprise-grade LLM evaluation standards and workflows.',
        ],
      },
      {
        role: 'Full-Stack Engineer',
        company: 'Labour Migration Agency Platform — Specialist Group',
        companyHref: 'https://labour-agency.vercel.app/',
        period: '2025',
        bullets: [
          'Delivered a production Labour Migration web platform and admin panel, measured by full client handoff, by building the complete stack with React/Next.js, Node.js, and PostgreSQL.',
          'Designed an admin panel for managing migration case records, measured by streamlined data entry and retrieval, by structuring a relational PostgreSQL schema with REST API endpoints.',
          'Optimized data flows between frontend and backend, measured by reduced query overhead, by implementing efficient API integration patterns end to end.',
        ],
      },
      {
        role: 'Frontend Engineer',
        company: 'Educational CRM & ERP Platform',
        period: 'Jan 2025 – Present',
        bullets: [
          'Reduced development cycles by 35%, measured by faster feature delivery, by architecting a TypeScript-first reusable component library across a modular ERP system.',
          'Improved UI responsiveness by 50%, measured by reduced redundant re-renders, by implementing a custom state-management middleware layer.',
          'Secured sensitive student data across 3+ administrative levels, measured by zero access-control incidents, by engineering a multi-tier RBAC system with REST API integration.',
        ],
      },
    ],
    education: EDUCATION_STANDARD,
    certifications: [
      'AI Frontend Engineering Certification — micro1 (U.S.-based company), 2026',
      "Prompt Engineering Certification — Najot Ta'lim, 2025",
      "Frontend System Architecture & React Ecosystem — Najot Ta'lim, 2025",
      "AI & Prompt Engineering for Developers — Najot Ta'lim, 2026",
    ],
    languages: LANGUAGES_STANDARD,
    accent: 'fuchsia',
    icon: 'sparkles',
  },

  'qa-tester': {
    slug: 'qa-tester',
    label: 'QA Tester',
    fullTitle: 'QA / Technical Support Engineer',
    tagline: 'API & Web Application Testing · AI-Accelerated Workflow (Claude Code)',
    summary: [
      'QA-minded engineer with a full-stack foundation: developer-level command of REST APIs, HTTP, JSON, client-server architecture, and SQL applied to testing and troubleshooting.',
      'Validated 40+ third-party API integrations, built automated test suites (Playwright, Vitest, Jest), and performed structured quality evaluations for a US company (micro1).',
      'Operates an AI-augmented workflow in which ~90% of routine QA and engineering tasks are executed through Claude Code under precise prompts, specs, and acceptance criteria — every output personally verified — delivering senior-level quality 10–20x faster than manual-only work, while focusing on exploratory testing, root-cause analysis, and customer communication.',
    ],
    heroStats: [
      { value: '40+', label: 'Third-Party APIs Validated' },
      { value: '10–20x', label: 'Faster via AI-Augmented QA' },
      { value: '3', label: 'Test Automation Frameworks' },
      { value: '90%', label: 'Routine QA Delegated to Claude Code' },
    ],
    competencies: [
      { category: 'QA & Testing', items: ['Manual Testing (Web & API)', 'Test Cases & Checklists', 'Regression Testing', 'Release Verification', 'Playwright', 'Vitest', 'Jest'] },
      { category: 'API Testing', items: ['Postman', 'REST APIs', 'HTTP Protocols', 'JSON', 'Swagger/OpenAPI Documentation'] },
      { category: 'Databases', items: ['SQL (PostgreSQL, Prisma ORM)', 'MongoDB (Working Knowledge)'] },
      { category: 'Defects & Documentation', items: ['Bug Reports with Reproduction Steps', 'GitHub Issues (Jira-style Workflow)', 'Technical Documentation', 'Knowledge Base Articles'] },
      { category: 'Troubleshooting', items: ['Application Log Analysis', 'Root-Cause Analysis', 'Client-Server Architecture', 'Production Debugging (Vercel)'] },
      { category: 'AI-Augmented Workflow', items: ['Claude Code (Agentic Task Execution)', 'Prompt Engineering', 'OpenAI / Claude / Gemini APIs', 'n8n Automation'] },
      { category: 'Web Stack', items: ['React 19', 'Next.js', 'TypeScript', 'Node.js', 'Express'] },
    ],
    howIWork: {
      title: 'How I Work — AI-Augmented Delivery with Claude Code',
      bullets: [
        'Direct Claude Code with detailed specs, prompts, and acceptance criteria to execute ~90% of routine engineering and QA work — generating test cases and checklists, writing regression suites, drafting bug reports and documentation, producing SQL validation queries, and triaging logs — then personally verify every result.',
        'Own the judgment layer myself: exploratory testing, defect prioritization, root-cause analysis, and customer communication. Net effect: senior-level output on routine tasks delivered 10–20x faster, compressing multi-day cycles into hours.',
      ],
    },
    experience: [
      {
        role: 'Full-Stack Engineer & AI Integration Developer',
        company: 'Era AI Platform',
        companyHref: 'https://era2-frontend.vercel.app/',
        period: '2025 – Present',
        bullets: [
          'Integrated and validated 40+ third-party AI tool APIs (REST/JSON): tested endpoints for correct responses, status codes, and error handling before each release, working with Postman and provider Swagger/OpenAPI documentation.',
          'Ran an AI-accelerated QA cycle: directed Claude Code to generate test cases, regression checklists, and Playwright suites from feature specs, then executed and manually verified every result — compressing multi-day testing cycles into hours.',
          'Diagnosed production incidents via Vercel deployment and server log analysis, tracing root causes across the Next.js frontend, Node.js API layer, and PostgreSQL database; validated data integrity with SQL and Prisma.',
        ],
      },
      {
        role: 'Full-Stack Developer',
        company: 'Labour Migration Agency Platform (Specialist Group)',
        companyHref: 'https://labour-agency.vercel.app/',
        period: '2025',
        bullets: [
          'Delivered and release-tested a production platform covering candidate intake forms, listings, and an admin management panel — verifying end-to-end flows across public and administrator roles before each deployment.',
          'Designed the PostgreSQL schema and REST API layer; wrote SQL validation queries to verify reliable data flow between public-facing forms and the admin dashboard.',
          'Implemented and tested Role-Based Access Control, documenting defects with clear reproduction steps in GitHub issue tracking during release verification.',
        ],
      },
      {
        role: 'AI Data Annotation & Quality Evaluation Contractor',
        company: 'micro1 (Titan Onyx Program, US Company)',
        period: '2026 – Present',
        bullets: [
          'Evaluated LLM outputs against strict guideline-adherence criteria — structured pass/fail quality assessments directly analogous to acceptance testing — contributing to model training and quality benchmarks.',
          'Wrote clear, detailed evaluation rationales in English for a US-based team, applying precise defect-style reporting across video, audio, and text modalities.',
        ],
      },
      {
        role: 'Frontend Engineer',
        company: 'Educational CRM & ERP Platform',
        period: 'Jan 2025 – Present',
        bullets: [
          'Reduced development cycle time by 35% by building a reusable, TypeScript-first component library for a modular ERP system.',
          'Secured sensitive student data across 3+ administrative access levels by engineering and testing a multi-tier Role-Based Access Control (RBAC) system.',
          'Achieved a 98/100 performance score via server-side rendering and dynamic code splitting; improved UI responsiveness by 50% with a custom state-management middleware layer.',
        ],
      },
    ],
    education: EDUCATION_STANDARD,
    certifications: [
      'AI Frontend Engineering Certification — micro1 (USA), 2026',
      "AI & Prompt Engineering for Developers — Najot Ta'lim, 2026",
      "Frontend System Architecture & React Ecosystem — Najot Ta'lim, 2025",
      'IELTS — Band 7+ (C1 Advanced English)',
    ],
    languages: LANGUAGES_STANDARD,
    accent: 'amber',
    icon: 'shield-check',
  },
}

export const categoryList: CategoryData[] = [
  categories['full-stack'],
  categories.frontend,
  categories['ai-specialist'],
  categories['qa-tester'],
]

export const categorySlugs: CategoryKey[] = ['full-stack', 'frontend', 'ai-specialist', 'qa-tester']

export function isCategoryKey(value: string): value is CategoryKey {
  return value === 'full-stack' || value === 'frontend' || value === 'ai-specialist' || value === 'qa-tester'
}

export const ACCENT_CLASSES: Record<CategoryData['accent'], { text: string; border: string; bg: string; from: string; dot: string }> = {
  sky:     { text: 'text-[#38bdf8]', border: 'border-[#38bdf8]/30', bg: 'bg-[#38bdf8]/10', from: 'from-sky-500 to-blue-600', dot: 'bg-[#38bdf8]' },
  violet:  { text: 'text-violet-400', border: 'border-violet-400/30', bg: 'bg-violet-400/10', from: 'from-violet-500 to-purple-600', dot: 'bg-violet-400' },
  fuchsia: { text: 'text-fuchsia-400', border: 'border-fuchsia-400/30', bg: 'bg-fuchsia-400/10', from: 'from-fuchsia-500 to-pink-600', dot: 'bg-fuchsia-400' },
  amber:   { text: 'text-amber-400', border: 'border-amber-400/30', bg: 'bg-amber-400/10', from: 'from-amber-500 to-orange-600', dot: 'bg-amber-400' },
}

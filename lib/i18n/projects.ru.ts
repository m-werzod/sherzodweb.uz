import type { Project } from '@/components/ui/ProjectCard'

/** Flagship platforms — architected end-to-end, shown first everywhere. */
export const flagshipProjects: Project[] = [
  {
    title: 'Платформа Era AI',
    description:
      'Full-stack платформа агрегации ИИ, объединяющая 40+ сторонних ИИ-инструментов в едином интерфейсе — спроектирована и полностью реализована мной в одиночку, от prompt-engineering пайплайнов до слоя данных PostgreSQL.',
    tags: ['React 19', 'Next.js', 'TypeScript', 'Node.js', 'PostgreSQL', 'Prisma', 'OpenAI API', 'Claude API', 'Gemini API'],
    github: 'https://github.com/m-werzod',
    demo: 'https://era2-frontend.vercel.app/',
    gradient: 'from-indigo-500 via-purple-500 to-fuchsia-600',
    image: '/images/projects/era-ai.png',
    status: 'live',
    year: '2026',
  },
  {
    title: 'Платформа агентства трудовой миграции',
    description:
      'Продакшн-платформа для частного кадрового агентства — формы приёма заявок кандидатов, список вакансий и полноценная административная панель, на основе реляционной схемы PostgreSQL и ролевого контроля доступа.',
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
  title: 'Платформа интернет-магазина',
  description:
    'Полнофункциональный интернет-магазин с каталогом товаров, административной панелью, поиском и фильтрами, корзиной покупок, аутентификацией пользователей и полностью адаптивным интерфейсом на всех устройствах.',
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
  homeHighlightPick,
  {
    title: 'Сайт ресторана',
    description:
      'Современный лендинг ресторана с интерактивным меню, системой бронирования столиков, анимированными секциями, фотогалереей и адаптивным дизайном с приоритетом на мобильные устройства.',
    tags: ['Next.js', 'TypeScript', 'Tailwind CSS', 'shadcn/ui', 'Lucide React', 'React Cookie'],
    github: 'https://github.com/m-werzod',
    demo: 'https://restaurant-ten-self.vercel.app/',
    gradient: 'from-orange-500 to-red-600',
    image: '/images/projects/restaurant.webp',
    status: 'live',
    year: '2024',
  },
  {
    title: 'Edu CRM / ERP система',
    description:
      'Платформа управления учебным заведением с учётом студентов, управлением курсами, посещаемостью, отчётами по успеваемости и удобной административной панелью для учебных заведений.',
    tags: ['React', 'TypeScript', 'Tailwind CSS', 'Ant Design', 'Axios', 'React Query', 'React Hot Toast', 'React Cookie'],
    github: 'https://github.com/m-werzod',
    demo: 'https://edu-crm-erp.vercel.app/',
    gradient: 'from-emerald-500 to-teal-600',
    image: '/images/projects/educrm.webp',
    status: 'live',
  },
  {
    title: 'Менеджер финансов бизнеса',
    description:
      'Full-stack приложение для управления финансами бизнеса с учётом доходов и расходов, планированием бюджета, историей транзакций, разбивкой по категориям и интерактивной аналитикой на дашборде.',
    tags: ['React', 'TypeScript', 'Next.js', 'Node.js', 'Tailwind CSS', 'Recharts', 'PostgreSQL', 'JWT'],
    github: 'https://github.com/m-werzod',
    demo: 'https://finance-manager-theta-six.vercel.app/',
    gradient: 'from-green-500 to-emerald-600',
    image: '/images/projects/finance.jpg',
    status: 'live',
  },
  {
    title: 'Turon Avtomaktab — платформа автошколы',
    description:
      'Продакшн-сайт автошколы с 7 филиалами в Намангане — каталог категорий прав, динамические цены на курсы, поиск филиалов, регистрация учеников с депозитом, раздел результатов и фотогалерея, полностью локализовано на узбекский, русский и английский языки.',
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
    title: 'Toshkent Baliqchi',
    description:
      'Лендинг рыбного ресторана с анимированными разделами меню, картой расположения, контактной формой и свежим дизайном в морской тематике, оптимизированным для мобильных устройств.',
    tags: ['React', 'Tailwind CSS', 'JavaScript'],
    github: 'https://github.com/m-werzod',
    demo: 'https://toshkent-baliqchi.vercel.app/',
    gradient: 'from-cyan-500 to-blue-500',
    image: '/images/projects/baliqchi.jpg',
    status: 'live',
  },
  {
    title: 'Nexora Labs — сайт компании',
    description:
      'Корпоративный сайт технологической компании с витриной услуг, разделом команды, анимированным hero-блоком и современной тёмной дизайн-системой.',
    tags: ['React', 'Next.js', 'Tailwind CSS'],
    github: 'https://github.com/m-werzod/Nexora-labs-company',
    demo: 'https://github.com/m-werzod/Nexora-labs-company',
    gradient: 'from-violet-500 to-purple-600',
    image: '/images/projects/nexora.jpg',
  },
  {
    title: 'iPhone Store UZ',
    description:
      'Интернет-магазин продукции Apple со списком товаров, фильтром по категориям, корзиной и попиксельным интерфейсом в стиле Apple для узбекского рынка.',
    tags: ['React', 'TypeScript', 'Tailwind CSS', 'Vite'],
    github: 'https://github.com/m-werzod/IPHONE-STORE.UZ',
    demo: 'https://github.com/m-werzod/IPHONE-STORE.UZ',
    gradient: 'from-slate-400 to-slate-600',
    image: '/images/projects/iphone-store.jpg',
  },
  {
    title: 'Fitness Time Gym',
    description:
      'Лендинг фитнес-клуба с тарифными планами, расписанием занятий, профилями тренеров, анимированным счётчиком статистики и ярким энергичным дизайном.',
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
      'Магазин элитной парфюмерии с карточками товаров, фильтрацией по категориям ароматов, списком желаний, корзиной и элегантным интерфейсом в стиле глассморфизм.',
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
      'Полноценный сайт ресторана с анимированным меню, онлайн-бронированием столиков, галереей, разделом отзывов клиентов и плавными переходами между страницами.',
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
      'Это самое портфолио — создано на Next.js 15, анимировано с помощью Framer Motion, с 3D-визуализацией через React Three Fiber и full-stack системой обратной связи с Telegram и Gmail.',
    tags: ['Next.js', 'TypeScript', 'Three.js', 'Tailwind CSS', 'React Three Fiber'],
    github: 'https://github.com/m-werzod',
    demo: 'https://sherzoddev.com',
    gradient: 'from-[#38bdf8] to-indigo-500',
    image: '/images/projects/portfolio.jpg',
    status: 'live',
  },
]

export const allProjects: Project[] = [...featuredProjects, ...moreProjects]

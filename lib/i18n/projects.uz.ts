import type { Project } from '@/components/ui/ProjectCard'

/** Flagship platforms — architected end-to-end, shown first everywhere. */
export const flagshipProjects: Project[] = [
  {
    title: 'Era AI Platform',
    description:
      "Bitta yagona interfeys ortida 40+ tashqi AI vositasini bog'lovchi full-stack AI agregatsiya platformasi — prompt muhandisligi quvurlaridan PostgreSQL ma'lumotlar qatlamigacha yakka o'zim loyihalashtirilgan va boshqarilgan.",
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
      "Xususiy bandlik agentligi uchun ishlab chiqarish darajasidagi platforma — nomzodlarni qabul qilish shakllari, bo'sh ish o'rinlari ro'yxati va to'liq admin boshqaruv paneli, relyatsion PostgreSQL sxemasi va rolga asoslangan kirish nazorati bilan quvvatlangan.",
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
  title: "Elektron Tijorat Platformasi",
  description:
    "Mahsulot katalogi, admin paneli, qidiruv va filtr, xarid savati, foydalanuvchi autentifikatsiyasi va barcha qurilmalarda to'liq moslashuvchan interfeysga ega to'liq funksional onlayn do'kon.",
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
    title: "Restoran Veb-sayti",
    description:
      "Interaktiv menyu, joy band qilish tizimi, animatsion bo'limlar, foto galereya va mobil-birinchi moslashuvchan dizaynga ega zamonaviy restoran landing sahifasi.",
    tags: ['Next.js', 'TypeScript', 'Tailwind CSS', 'shadcn/ui', 'Lucide React', 'React Cookie'],
    github: 'https://github.com/m-werzod',
    demo: 'https://restaurant-ten-self.vercel.app/',
    gradient: 'from-orange-500 to-red-600',
    image: '/images/projects/restaurant.webp',
    status: 'live',
    year: '2024',
  },
  {
    title: "Edu CRM / ERP Tizimi",
    description:
      "Talabalarni kuzatish, kurslarni boshqarish, davomat, baholar hisobotlari va ta'lim muassasalari uchun toza admin paneliga ega ta'lim boshqaruvi platformasi.",
    tags: ['React', 'TypeScript', 'Tailwind CSS', 'Ant Design', 'Axios', 'React Query', 'React Hot Toast', 'React Cookie'],
    github: 'https://github.com/m-werzod',
    demo: 'https://edu-crm-erp.vercel.app/',
    gradient: 'from-emerald-500 to-teal-600',
    image: '/images/projects/educrm.webp',
    status: 'live',
  },
  {
    title: "Biznes Moliyasini Boshqarish Tizimi",
    description:
      "Daromad va xarajatlarni kuzatish, byudjet rejalashtirish, tranzaksiyalar tarixi, toifalar bo'yicha taqsimot va interaktiv panel tahlili bilan full-stack biznes-moliya boshqaruv ilovasi.",
    tags: ['React', 'TypeScript', 'Next.js', 'Node.js', 'Tailwind CSS', 'Recharts', 'PostgreSQL', 'JWT'],
    github: 'https://github.com/m-werzod',
    demo: 'https://finance-manager-theta-six.vercel.app/',
    gradient: 'from-green-500 to-emerald-600',
    image: '/images/projects/finance.jpg',
    status: 'live',
  },
]

/** The rest of the catalogue — shown under "More Work" on the full /projects page. */
export const moreProjects: Project[] = [
  {
    title: 'Toshkent Baliqchi',
    description:
      "Animatsion menyu bo'limlari, joylashuv xaritasi, aloqa shakli va mobil uchun optimallashtirilgan yangi dengiz mavzusidagi interfeysga ega baliq restorani landing sahifasi.",
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
      "Xizmatlar vitrinasi, jamoa bo'limi, animatsion hero va zamonaviy qorong'i dizayn tizimiga ega texnologiya kompaniyasi uchun korporativ veb-sayt.",
    tags: ['React', 'Next.js', 'Tailwind CSS'],
    github: 'https://github.com/m-werzod/Nexora-labs-company',
    demo: 'https://github.com/m-werzod/Nexora-labs-company',
    gradient: 'from-violet-500 to-purple-600',
    image: '/images/projects/nexora.jpg',
  },
  {
    title: 'iPhone Store UZ',
    description:
      "O'zbekiston bozori uchun mahsulot ro'yxati, toifa filtri, savat va piksel darajasida aniq Apple uslubidagi interfeysga ega Apple mahsulotlari elektron tijorat do'koni.",
    tags: ['React', 'TypeScript', 'Tailwind CSS', 'Vite'],
    github: 'https://github.com/m-werzod/IPHONE-STORE.UZ',
    demo: 'https://github.com/m-werzod/IPHONE-STORE.UZ',
    gradient: 'from-slate-400 to-slate-600',
    image: '/images/projects/iphone-store.jpg',
  },
  {
    title: 'Fitness Time Gym',
    description:
      "Narx rejalari, mashg'ulotlar jadvali, murabbiylar profillari, animatsion statistika hisoblagichi va o'ktam, yuqori energiyali dizaynga ega sportzal landing sahifasi.",
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
      "Mahsulot kartochkalari, hid toifasi bo'yicha filtrlash, sevimlilar ro'yxati, savat va nafis glassmorphism interfeysga ega hashamatli atir do'koni.",
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
      "Animatsion menyu, onlayn stol band qilish, galereya, mijozlar sharhlari bo'limi va silliq sahifa o'tishlariga ega to'liq restoran veb-sayti.",
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
      "Ushbu portfolio — Next.js 15 bilan qurilgan, Framer Motion bilan animatsiyalangan, React Three Fiber orqali 3D vizuallar va Telegram hamda Gmail bilan full-stack aloqa tizimiga ega.",
    tags: ['Next.js', 'TypeScript', 'Three.js', 'Tailwind CSS', 'React Three Fiber'],
    github: 'https://github.com/m-werzod',
    demo: 'https://sherzoddev.com',
    gradient: 'from-[#38bdf8] to-indigo-500',
    image: '/images/projects/portfolio.jpg',
    status: 'live',
  },
]

export const allProjects: Project[] = [...featuredProjects, ...moreProjects]

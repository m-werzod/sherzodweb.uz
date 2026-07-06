import type { CategoryData, CategoryKey } from '@/lib/resumeData'

const LANGUAGES_STANDARD_UZ = [
  { name: "O'zbek tili", flag: 'https://flagcdn.com/w80/uz.png', level: 'Ona tili', fill: 100 },
  { name: 'Ingliz tili', flag: 'https://flagcdn.com/w80/gb.png', level: "Erkin — C1, IELTS 7+ ball", fill: 90 },
  { name: 'Rus tili', flag: 'https://flagcdn.com/w80/ru.png', level: 'Muloqot darajasida', fill: 45 },
]

const EDUCATION_STANDARD_UZ = ["Biznesni Boshqarish bakalavri — Toshkent Davlat Iqtisodiyot Universiteti (Davom Etmoqda)"]

export const categories: Record<CategoryKey, CategoryData> = {
  'full-stack': {
    slug: 'full-stack',
    label: 'Full Stack',
    fullTitle: "Full-Stack Dasturchi",
    tagline: "Node.js · TypeScript · React 19 · Next.js · Python · .NET · AI Integratsiyasi",
    summary: [
      "Ishlab chiqarish darajasidagi veb-ilovalarni boshidan-oxirigacha quruvchi Full-Stack Dasturchi — Node.js, Express va PostgreSQL/Prisma backendlari ustida React 19 / Next.js frontendlari — micro1 (Qo'shma Shtatlar) tomonidan xalqaro sertifikatlangan Frontend Engineer Expert.",
      "Beshta jonli platforma (korporativ ERP, elektron tijorat, fintech SaaS va AI mahsulotlari) bo'yicha isbotlangan, o'lchanadigan natijalar: 98/100 Lighthouse bali, 50% kamroq ortiqcha re-render va 40% past server so'rov hajmi. Hozirda bitta yagona interfeys ortida 40+ AI vosita va API'ni birlashtiruvchi full-stack platforma — Era AI'ni loyihalashtirmoqdaman.",
      "Backend qamrovi Python (Django, skriptlash va avtomatlashtirish) va .NET (C# / ASP.NET Core)gacha kengaygan, shu bilan birga tur-xavfsiz arxitektura (generics, Zod) va AI bilan kuchaytirilgan yetkazib berish (Claude Code, Cursor AI) orqali 10x tezroq ishlab chiqarish.",
    ],
    heroStats: [
      { value: '5+', label: "Ishga Tushirilgan Jonli Platformalar" },
      { value: '40+', label: "Integratsiya Qilingan AI API'lar" },
      { value: '98/100', label: "Lighthouse Bali" },
      { value: '10x', label: "AI Bilan Kuchaytirilgan Yetkazishda Tezroq" },
    ],
    competencies: [
      { category: "Tillar", items: ['TypeScript (Advanced Generics, Mapped Types, Zod)', 'JavaScript (ES6+/ESNext)', 'Python', 'SQL', 'C# (Working Knowledge)'] },
      { category: "Backend va API'lar", items: ['Node.js', 'Express', 'REST & GraphQL API Design', 'PostgreSQL', 'Prisma ORM', 'MongoDB', 'Django (Working Knowledge)', '.NET / ASP.NET Core', 'Clerk / NextAuth / JWT'] },
      { category: "Frontend Muhandisligi", items: ['React 19', 'Next.js (App Router, SSR, Server Actions)', 'Redux Toolkit', 'TanStack Query v5', 'Tailwind CSS'] },
      { category: "AI Integratsiyasi va Avtomatlashtirish", items: ['OpenAI / Claude / Gemini APIs', 'Prompt Engineering', 'n8n Workflow Automation', 'Claude Code', 'Cursor AI', 'GitHub Copilot'] },
      { category: "Testlash va Unumdorlik", items: ['Vitest', 'Jest', 'Playwright', 'Core Web Vitals', 'Lighthouse Optimization'] },
      { category: "Arxitektura va DevOps", items: ['RBAC', 'Monorepo (Turborepo)', 'Git/GitHub', 'CI/CD', 'Vercel', 'Docker (Basics)'] },
    ],
    experience: [
      {
        role: "Full-Stack Muhandis va AI Integratsiya Dasturchisi",
        company: 'Era AI Platform',
        companyHref: 'https://era2-frontend.vercel.app/',
        period: "2026 – Hozirgacha",
        bullets: [
          "React 19, Next.js va TypeScript yordamida qurilgan yagona interfeys ortida 40+ tashqi AI vosita va API'ni birlashtiruvchi full-stack AI agregatsiya platformasi — Era AI'ni loyihalashtirdim va ishga tushirdim.",
          "Yakka dasturchi sifatida butun texnologik stekni boshqaraman — tur-xavfsiz frontend, Node.js xizmatlari va PostgreSQL/Prisma ma'lumotlar qatlami — ishlab chiqarishda uzluksiz funksiyalar kengayishini ta'minlab.",
          "Bir nechta LLM provayderlari (OpenAI, Claude, Gemini) bo'yicha natijalarni standartlashtirish va optimallashtirish uchun prompt muhandisligini qo'lladim, bu esa foydalanuvchilar uchun javoblar barqarorligini oshirdi.",
          "AI vosita ro'yxatlari, foydalanuvchi o'zaro ta'sirlari va tizimlarni boshidan-oxirigacha bog'lovchi avtomatlashtirilgan workflowlar uchun moslashuvchan admin uslubidagi boshqaruv interfeysini yaratdim.",
        ],
      },
      {
        role: "AI va LLM Baholash Bo'yicha Pudratchi",
        company: 'micro1 (United States) — Titan Onyx Program',
        period: '2026 – Hozirgacha',
        bullets: [
          "AQSHlik AI kompaniyasi uchun bir nechta katta til modellari natijalarini qat'iy ko'rsatma mezonlariga nisbatan baholayman va kalibrlayman, bu esa model o'qitish va sifat ko'rsatkichlariga bevosita hissa qo'shadi.",
          "React, TypeScript va tizim dizayni ko'nikmalarini mustaqil nazorat ostida sinovdan o'tkazish orqali micro1'ning xalqaro tan olingan Frontend Engineer Expert sertifikatini oldim.",
        ],
      },
      {
        role: "Full-Stack Dasturchi",
        company: 'Labour Migration Agency Platform (Specialist Group)',
        companyHref: 'https://labour-agency.vercel.app/',
        period: '2026',
        bullets: [
          "Xususiy bandlik agentligi uchun nomzodlarni qabul qilish shakllari, bo'sh ish o'rinlari ro'yxati va to'liq admin boshqaruv panelini qamrab olgan ishlab chiqarish darajasidagi platformani yetkazib berdim.",
          "Next.js frontendni backend xizmatlari bilan bog'lovchi PostgreSQL sxemasi va REST API qatlamini loyihalashtirdim, bu esa ommaviy shakllar va admin paneli o'rtasida ishonchli ma'lumotlar oqimini ta'minladi.",
          "Bitta joylashtirilgan tizim ichida administrator va nomzodga mo'ljallangan funksionallikni aniq ajratish uchun Rolga Asoslangan Kirish Nazorati (RBAC) tizimini joriy qildim.",
        ],
      },
      {
        role: "Full-Stack Frontend Muhandisi",
        company: 'Business Finance Manager (SaaS)',
        period: '2026',
        bullets: [
          "TypeScript va Next.js'da Prisma'dan UI'gacha 100% tur-xavfsiz ma'lumotlar oqimiga ega tur-xavfsiz biznes-moliya SaaS'ini loyihalashtirdim, natijada 97/100 Lighthouse bali qo'lga kiritdim.",
          "TanStack Query'ning optimistik yangilanishlari va avtomatik keshni bekor qilish yordamida real vaqt rejimidagi pul oqimi tahlili panelini yaratdim — sezilgan yuklash vaqtini 60% ga qisqartirdi.",
          "10 000+ dan ortiq moliyaviy tranzaksiyalardan iborat ma'lumotlar to'plamlarida UI kechikishisiz silliq ishlaydigan yuqori unumdor ma'lumotlarni vizualizatsiya qilish modullarini ishlab chiqdim.",
          "Barcha moliyaviy kiritishlar bo'yicha boshidan-oxirigacha Zod sxema validatsiyasini joriy qildim, bu esa tranzaksiya sikli davomida runtime xatolarini bartaraf etdi.",
        ],
      },
      {
        role: "Frontend Muhandisi",
        company: 'Educational CRM & ERP Platform',
        period: '2026',
        bullets: [
          "TypeScript-birinchi qayta ishlatiladigan komponentlar kutubxonasini yaratish va murakkab Figma dizaynlarini piksel darajasida aniq, moslashuvchan UI'ga aylantirish orqali ishlab chiqish siklini 35% ga qisqartirdim.",
          "Korporativ miqyosda ortiqcha re-renderlarni bartaraf etadigan maxsus state-management middleware qatlami orqali UI tezkorligini 50% ga oshirdim.",
          "3+ ma'muriy daraja bo'yicha ko'p pog'onali RBAC tizimini yaratdim, bu esa nozik talaba ma'lumotlarini himoyalab, uzluksiz va yuqori tezlikdagi foydalanuvchi tajribasini saqlab qoldi.",
        ],
      },
      {
        role: "Frontend Dasturchi",
        company: 'E-Commerce Storefront (Toshkent Baliqchi)',
        period: '2025',
        bullets: [
          "Next.js App Router va Tailwind CSS bilan yuqori tranzaksion SSR do'konini joylashtirdim, soniyadan qisqa sahifa o'tishlari bilan SEO indekslashni 25% ga oshirdim.",
          "500+ SKU inventarni nol kechikishli asinxron yangilanishlar bilan boshqarish uchun global holatni Redux Toolkit yordamida qayta qurdim.",
          "Maxsus debounce qilingan qidiruv tizimi va ko'p mezonli filtrlash tizimini yaratdim, server tomonidagi so'rovlar hajmini 40% ga qisqartirdi.",
        ],
      },
    ],
    education: EDUCATION_STANDARD_UZ,
    certifications: [
      "Frontend Engineer Expert Sertifikati — micro1 (Qo'shma Shtatlar), 2026 — xalqaro tan olingan, mustaqil nazorat ostida topshirilgan",
      "Frontend Engineering Dasturi — Najot Ta'lim, 2025–2026 — Tamomlagan",
      "AI Prompt Engineering (IT Yo'nalishi) — Najot Ta'lim, 2026 — Tamomlagan",
    ],
    languages: LANGUAGES_STANDARD_UZ,
    accent: 'sky',
    icon: 'code',
  },

  frontend: {
    slug: 'frontend',
    label: 'Frontend',
    fullTitle: 'Frontend Engineer Expert',
    tagline: "TypeScript · React 19 · Next.js · AI Integratsiya Mutaxassisi",
    summary: [
      "TypeScript bo'yicha ekspert Frontend Muhandisi, ishlab chiqarish darajasidagi React 19 va Next.js ilovalarini quradi, micro1 (Qo'shma Shtatlar) tomonidan xalqaro sertifikatlangan Frontend Engineer Expert.",
      "Beshta jonli platforma — korporativ ERP, elektron tijorat, fintech SaaS va AI mahsulotlari bo'yicha isbotlangan, o'lchanadigan natijalar: 98/100 Lighthouse bali, 50% kamroq ortiqcha re-render va 40% past server so'rov hajmi. Hozirda bitta yagona interfeys ortida 40+ AI vosita va API'ni birlashtiruvchi full-stack platforma — Era AI'ni loyihalashtirmoqdaman.",
      "Ilg'or tur-xavfsiz arxitektura (generics, mapped types, Zod)ni full-stack qamrov (Node.js, PostgreSQL, Prisma) va AI bilan kuchaytirilgan yetkazib berish (Claude Code, Cursor AI) bilan birlashtirib, 10x tezroq ishlab chiqarishni ta'minlaydi.",
    ],
    heroStats: [
      { value: '98/100', label: "Lighthouse Bali" },
      { value: '50%', label: "Kamroq Ortiqcha Re-render" },
      { value: '40%', label: "Past Server So'rov Hajmi" },
      { value: '5', label: "Ishga Tushirilgan Jonli Platformalar" },
    ],
    competencies: [
      { category: "TypeScript va JavaScript", items: ['Advanced Generics', 'Mapped & Utility Types', 'Type-Safe API Contracts', 'Zod Schema Validation', 'ES6+/ESNext', 'Functional Programming'] },
      { category: "Frontend Muhandisligi", items: ['React 19', 'Next.js (App Router, SSR, Server Actions)', 'Redux Toolkit', 'TanStack Query v5', 'Tailwind CSS', 'HTML5/CSS3', 'WCAG Accessibility'] },
      { category: "Backend va API'lar", items: ['Node.js', 'Express', 'PostgreSQL', 'Prisma ORM', 'REST & GraphQL API Design', 'Clerk / NextAuth'] },
      { category: "AI Integratsiyasi va Avtomatlashtirish", items: ['OpenAI / Claude / Gemini APIs', 'Prompt Engineering', 'n8n Workflow Automation', 'Claude Code', 'Cursor AI', 'GitHub Copilot'] },
      { category: "Testlash va Unumdorlik", items: ['Vitest', 'Jest', 'Playwright', 'Core Web Vitals', 'Dynamic Code Splitting', 'Memoization', 'Web Workers'] },
      { category: "Arxitektura va DevOps", items: ['Reusable Component Libraries', 'Atomic Design', 'RBAC', 'Micro-Frontend Patterns', 'Turborepo', 'CI/CD', 'Vercel'] },
    ],
    experience: [
      {
        role: "Full-Stack Muhandis va AI Integratsiya Dasturchisi",
        company: 'Era AI Platform',
        companyHref: 'https://era2-frontend.vercel.app/',
        period: "2026 – Hozirgacha",
        bullets: [
          "React 19, Next.js va TypeScript yordamida qurilgan yagona interfeys ortida 40+ tashqi AI vosita va API'ni birlashtiruvchi full-stack AI agregatsiya platformasi — Era AI'ni loyihalashtirdim va ishga tushirdim.",
          "Yakka dasturchi sifatida butun texnologik stekni boshqaraman — tur-xavfsiz frontend, Node.js xizmatlari va PostgreSQL/Prisma ma'lumotlar qatlami — ishlab chiqarishda uzluksiz funksiyalar kengayishini ta'minlab.",
          "Bir nechta LLM provayderlari (OpenAI, Claude, Gemini) bo'yicha natijalarni standartlashtirish va optimallashtirish uchun prompt muhandisligini qo'lladim, bu esa foydalanuvchilar uchun javoblar barqarorligini oshirdi.",
          "AI vosita ro'yxatlari, foydalanuvchi o'zaro ta'sirlari va tizimlarni boshidan-oxirigacha bog'lovchi avtomatlashtirilgan workflowlar uchun moslashuvchan admin uslubidagi boshqaruv interfeysini yaratdim.",
        ],
      },
      {
        role: "AI va LLM Baholash Bo'yicha Pudratchi",
        company: 'micro1 (United States) — Titan Onyx Program',
        period: '2026 – Hozirgacha',
        bullets: [
          "AQSHlik AI kompaniyasi uchun bir nechta katta til modellari natijalarini qat'iy ko'rsatma mezonlariga nisbatan baholayman va kalibrlayman, bu esa model o'qitish va sifat ko'rsatkichlariga bevosita hissa qo'shadi.",
          "React, TypeScript va tizim dizayni ko'nikmalarini mustaqil nazorat ostida sinovdan o'tkazish orqali micro1'ning xalqaro tan olingan Frontend Engineer Expert sertifikatini oldim.",
        ],
      },
      {
        role: "Full-Stack Dasturchi",
        company: 'Labour Migration Agency Platform (Specialist Group)',
        companyHref: 'https://labour-agency.vercel.app/',
        period: '2026',
        bullets: [
          "Xususiy bandlik agentligi uchun nomzodlarni qabul qilish shakllari, bo'sh ish o'rinlari ro'yxati va to'liq admin boshqaruv panelini qamrab olgan ishlab chiqarish darajasidagi platformani yetkazib berdim.",
          "Next.js frontendni backend xizmatlari bilan bog'lovchi PostgreSQL sxemasi va REST API qatlamini loyihalashtirdim, bu esa ommaviy shakllar va admin paneli o'rtasida ishonchli ma'lumotlar oqimini ta'minladi.",
          "Bitta joylashtirilgan tizim ichida administrator va nomzodga mo'ljallangan funksionallikni aniq ajratish uchun Rolga Asoslangan Kirish Nazorati (RBAC) tizimini joriy qildim.",
        ],
      },
      {
        role: "Full-Stack Frontend Muhandisi",
        company: 'Business Finance Manager (SaaS)',
        period: '2026',
        bullets: [
          "TypeScript va Next.js'da Prisma'dan UI'gacha 100% tur-xavfsiz ma'lumotlar oqimiga ega tur-xavfsiz biznes-moliya SaaS'ini loyihalashtirdim, natijada 97/100 Lighthouse bali qo'lga kiritdim.",
          "TanStack Query'ning optimistik yangilanishlari va avtomatik keshni bekor qilish yordamida real vaqt rejimidagi pul oqimi tahlili panelini yaratdim — sezilgan yuklash vaqtini 60% ga qisqartirdi.",
          "10 000+ dan ortiq moliyaviy tranzaksiyalardan iborat ma'lumotlar to'plamlarida UI kechikishisiz silliq ishlaydigan yuqori unumdor ma'lumotlarni vizualizatsiya qilish modullarini ishlab chiqdim.",
        ],
      },
      {
        role: "Frontend Muhandisi",
        company: 'Educational CRM & ERP Platform',
        period: '2026',
        bullets: [
          "TypeScript-birinchi qayta ishlatiladigan komponentlar kutubxonasini yaratish va murakkab Figma dizaynlarini piksel darajasida aniq, moslashuvchan UI'ga aylantirish orqali ishlab chiqish siklini 35% ga qisqartirdim.",
          "Korporativ miqyosda ortiqcha re-renderlarni bartaraf etadigan maxsus state-management middleware qatlami orqali UI tezkorligini 50% ga oshirdim.",
          "Server-Side Rendering, dinamik kod bo'lish va CSS/aktiv optimallashtiruvi orqali 98/100 Lighthouse unumdorlik balini qo'lga kiritdim.",
        ],
      },
      {
        role: "Frontend Dasturchi",
        company: 'E-Commerce Storefront (Toshkent Baliqchi)',
        period: '2025',
        bullets: [
          "Next.js App Router va Tailwind CSS bilan yuqori tranzaksion SSR do'konini joylashtirdim, barcha qurilmalarda soniyadan qisqa sahifa o'tishlari bilan SEO indekslashni 25% ga oshirdim.",
          "500+ SKU inventarni nol kechikishli asinxron yangilanishlar bilan boshqarish uchun global holatni Redux Toolkit yordamida qayta qurdim.",
          "Maxsus debounce qilingan qidiruv tizimi va ko'p mezonli filtrlash tizimini yaratdim, server tomonidagi so'rovlar hajmini 40% ga qisqartirdi.",
        ],
      },
    ],
    education: EDUCATION_STANDARD_UZ,
    certifications: [
      "Frontend Engineer Expert Sertifikati — micro1 (Qo'shma Shtatlar), 2026 — xalqaro tan olingan, mustaqil nazorat ostida topshirilgan",
      "Frontend Engineering Dasturi — Najot Ta'lim, 2025–2026 — Tamomlagan",
      "AI Prompt Engineering (IT Yo'nalishi) — Najot Ta'lim, 2026 — Tamomlagan",
    ],
    languages: LANGUAGES_STANDARD_UZ,
    accent: 'violet',
    icon: 'layout',
  },

  'ai-specialist': {
    slug: 'ai-specialist',
    label: "AI Mutaxassisi",
    fullTitle: "AI Dasturiy Ta'minot Muhandisi",
    tagline: "Full-Stack Dasturchi · Prompt Muhandisligi Mutaxassisi",
    summary: [
      "Katta til modellarini (OpenAI, Claude, Gemini, Mistral) prompt muhandisligi va API avtomatlashtiruvi orqali ishlab chiqarish darajasidagi veb-platformalarga integratsiya qilishga ixtisoslashgan, AI yo'naltirilgan Full-Stack Dasturiy Ta'minot Muhandisi.",
      "API orqali 40+ AI vositasini bog'lovchi full-stack AI agregatsiya platformasi — Era AI'ni mustaqil ravishda loyihalashtirdim va joylashtirdim, shu bilan birga PostgreSQL bilan quvvatlangan korporativ darajadagi React/Next.js/Node.js ilovalarini yaratdim.",
      "Amaliy AI model baholash tajribasini o'zbek tilini ona tili darajasida (C2) va ingliz tilini erkin (C1, IELTS 7+) bilish bilan birlashtiradi, bu esa g'oyadan joylashtirishgacha AI quvvatidagi platformalar, admin panellari va avtomatlashtirish tizimlarini qurishga tayyor ko'p funksiyali hamkor sifatida namoyon bo'ladi.",
    ],
    heroStats: [
      { value: '40+', label: "API Orqali Integratsiya Qilingan AI Vositalari" },
      { value: '4', label: "Boshqarilgan LLM Provayderlari" },
      { value: '98/100', label: "Lighthouse Bali" },
      { value: '1', label: "Yakka Boshqarilayotgan Ishlab Chiqarishdagi AI Platforma" },
    ],
    competencies: [
      { category: "AI va LLM Muhandisligi", items: ['LLM Integration (OpenAI, Claude, Gemini, Mistral)', 'Prompt Engineering', 'AI Workflow Automation', 'AI Chatbot Development'] },
      { category: "Backend va Avtomatlashtirish", items: ['Python (Scripting & Automation)', 'Node.js', 'REST API Design & Integration', 'n8n Workflow Automation'] },
      { category: "Ma'lumotlar Bazasi", items: ['PostgreSQL', 'MySQL', 'SQL', 'Prisma ORM'] },
      { category: "Frontend va Admin Tizimlari", items: ['React', 'Next.js', 'TypeScript', 'Admin Panel Development'] },
      { category: "Versiya Nazorati va DevOps", items: ['Git', 'GitHub', 'CI/CD Pipelines', 'Vercel Deployment'] },
    ],
    experience: [
      {
        role: "Full-Stack AI Muhandisi",
        company: 'Era AI Platform',
        companyHref: 'https://era2-frontend.vercel.app/',
        period: "2026 – Hozirgacha",
        bullets: [
          "Node.js va Python skriptli avtomatlashtirish backendi ustida React 19/Next.js frontendini qurish orqali, bitta interfeysdan foydalanish mumkin bo'lgan 40+ integratsiya qilingan AI vositasi bilan o'lchanadigan full-stack AI agregatsiya platformasi — Era AI'ni loyihalashtirdim va ishga tushirdim.",
          "Qayta ishlatiladigan prompt muhandisligi quvurlari va API abstraksiya qatlamlarini loyihalashtirish orqali, oxirgi foydalanuvchilar uchun uzluksiz model almashtirish bilan o'lchanadigan ko'p modelli LLM integratsiyalarini (OpenAI, Claude, Gemini, Mistral) boshqardim.",
          "Arxitekturadan Vercel'da joylashtirishgacha bo'lgan to'liq ishlab chiqish siklini mustaqil boshqarish orqali, ishga tushirilgandan keyin davom etayotgan funksiya chiqarishlari bilan o'lchanadigan platformaning uzluksiz yakka boshqaruvini saqladim.",
        ],
      },
      {
        role: "AI Instruktor va Baholovchi",
        company: 'micro1 — Titan Onyx Program (U.S.-based)',
        period: '2026',
        bullets: [
          "Tuzilgan video/audio izohlash, transkripsiya va AI skrining baholashlarini o'tkazish orqali, yuzlab topshiriqlar bo'yicha baholash ko'rsatmalariga izchil rioya qilish bilan o'lchanadigan AI model natijalarini baholadim va kalibrladim.",
          "Kontent moderatsiyasi va javob sifatini baholash workflowlariga prompt muhandisligi bo'yicha xulosalarni qo'llash orqali, ko'rsatma mezonlariga nisbatan kalibratsiya aniqligi bilan o'lchanadigan model javoblari sifatini oshirdim.",
          "AQSHda joylashgan AI o'qitish kompaniyasi uchun xalqaro pudratchi sifatida ishladim, korporativ darajadagi LLM baholash standartlari va workflowlari bilan bevosita tanishdim.",
        ],
      },
      {
        role: "Full-Stack Muhandis",
        company: 'Labour Migration Agency Platform — Specialist Group',
        companyHref: 'https://labour-agency.vercel.app/',
        period: '2025',
        bullets: [
          "React/Next.js, Node.js va PostgreSQL bilan to'liq stekni qurish orqali, mijozga to'liq topshirish bilan o'lchanadigan ishlab chiqarish darajasidagi Labour Migration veb-platformasi va admin panelini yetkazib berdim.",
          "REST API endpointlari bilan relyatsion PostgreSQL sxemasini tuzish orqali, soddalashtirilgan ma'lumot kiritish va olish bilan o'lchanadigan migratsiya ishlari yozuvlarini boshqarish uchun admin panelini loyihalashtirdim.",
          "Boshidan-oxirigacha samarali API integratsiya patternlarini joriy qilish orqali, kamaytirilgan so'rov yukini o'lchaydigan frontend va backend o'rtasidagi ma'lumotlar oqimini optimallashtirdim.",
        ],
      },
      {
        role: "Frontend Muhandisi",
        company: 'Educational CRM & ERP Platform',
        period: "2025-yil Yanvar – Hozirgacha",
        bullets: [
          "Modulli ERP tizimi bo'yicha TypeScript-birinchi qayta ishlatiladigan komponentlar kutubxonasini loyihalashtirish orqali, tezroq funksiya yetkazib berish bilan o'lchanadigan ishlab chiqish siklini 35% ga qisqartirdim.",
          "Maxsus state-management middleware qatlamini joriy qilish orqali, kamaytirilgan ortiqcha re-renderlar bilan o'lchanadigan UI tezkorligini 50% ga oshirdim.",
          "REST API integratsiyasi bilan ko'p pog'onali RBAC tizimini yaratish orqali, nol kirish nazorati hodisalari bilan o'lchanadigan nozik talaba ma'lumotlarini 3+ ma'muriy daraja bo'yicha himoyaladim.",
        ],
      },
    ],
    education: EDUCATION_STANDARD_UZ,
    certifications: [
      "AI Frontend Engineering Sertifikati — micro1 (AQSHda joylashgan kompaniya), 2026",
      "Prompt Engineering Sertifikati — Najot Ta'lim, 2025",
      "Frontend Tizim Arxitekturasi va React Ekotizimi — Najot Ta'lim, 2025",
      "Dasturchilar uchun AI va Prompt Engineering — Najot Ta'lim, 2026",
    ],
    languages: LANGUAGES_STANDARD_UZ,
    accent: 'fuchsia',
    icon: 'sparkles',
  },

  'qa-tester': {
    slug: 'qa-tester',
    label: 'QA Tester',
    fullTitle: "QA / Texnik Yordam Muhandisi",
    tagline: "API va Veb-Ilova Testlash · AI Bilan Tezlashtirilgan Workflow (Claude Code)",
    summary: [
      "Full-stack asosga ega QA fikrlaydigan muhandis: testlash va nosozliklarni bartaraf etishga qo'llaniladigan REST API, HTTP, JSON, mijoz-server arxitekturasi va SQL'ni dasturchi darajasida bilish.",
      "40+ tashqi API integratsiyasini tekshirdim, avtomatlashtirilgan test to'plamlarini (Playwright, Vitest, Jest) yaratdim va AQSHlik kompaniya (micro1) uchun tuzilgan sifat baholashlarini o'tkazdim.",
      "Aniq promptlar, spetsifikatsiyalar va qabul qilish mezonlari ostida oddiy QA va muhandislik topshiriqlarining ~90% Claude Code orqali bajariladigan AI bilan kuchaytirilgan workflow'ni boshqaraman — har bir natija shaxsan tekshiriladi — faqat qo'lda bajariladigan ishga qaraganda 10–20x tezroq senior darajadagi sifatni yetkazib beraman, shu bilan birga tadqiqiy testlash, ildiz sababini tahlil qilish va mijozlar bilan muloqotga e'tibor qarataman.",
    ],
    heroStats: [
      { value: '40+', label: "Tekshirilgan Tashqi API'lar" },
      { value: '10–20x', label: "AI Bilan Kuchaytirilgan QA Orqali Tezroq" },
      { value: '3', label: "Test Avtomatlashtirish Freymvorklari" },
      { value: '90%', label: "Claude Code'ga Topshirilgan Oddiy QA" },
    ],
    competencies: [
      { category: "QA va Testlash", items: ['Manual Testing (Web & API)', 'Test Cases & Checklists', 'Regression Testing', 'Release Verification', 'Playwright', 'Vitest', 'Jest'] },
      { category: "API Testlash", items: ['Postman', 'REST APIs', 'HTTP Protocols', 'JSON', 'Swagger/OpenAPI Documentation'] },
      { category: "Ma'lumotlar Bazalari", items: ['SQL (PostgreSQL, Prisma ORM)', 'MongoDB (Working Knowledge)'] },
      { category: "Nuqsonlar va Hujjatlashtirish", items: ['Bug Reports with Reproduction Steps', 'GitHub Issues (Jira-style Workflow)', 'Technical Documentation', 'Knowledge Base Articles'] },
      { category: "Nosozliklarni Bartaraf Etish", items: ['Application Log Analysis', 'Root-Cause Analysis', 'Client-Server Architecture', 'Production Debugging (Vercel)'] },
      { category: "AI Bilan Kuchaytirilgan Workflow", items: ['Claude Code (Agentic Task Execution)', 'Prompt Engineering', 'OpenAI / Claude / Gemini APIs', 'n8n Automation'] },
      { category: "Veb Steki", items: ['React 19', 'Next.js', 'TypeScript', 'Node.js', 'Express'] },
    ],
    howIWork: {
      title: "Qanday Ishlayman — Claude Code Bilan AI Bilan Kuchaytirilgan Yetkazib Berish",
      bullets: [
        "Oddiy muhandislik va QA ishlarining ~90%ini bajarish uchun Claude Code'ga batafsil spetsifikatsiyalar, promptlar va qabul qilish mezonlarini beraman — test keyslari va checklistlar yaratish, regressiya to'plamlarini yozish, xato hisobotlari va hujjatlarni tayyorlash, SQL validatsiya so'rovlarini yaratish va loglarni saralash — so'ngra har bir natijani shaxsan tekshiraman.",
        "Qaror qabul qilish qatlamini o'zim boshqaraman: tadqiqiy testlash, nuqsonlarni ustuvorlashtirish, ildiz sababini tahlil qilish va mijozlar bilan muloqot. Yakuniy natija: oddiy topshiriqlarda 10–20x tezroq yetkaziladigan senior darajadagi natija, ko'p kunlik sikllarni soatlarga siqib.",
      ],
    },
    experience: [
      {
        role: "Full-Stack Muhandis va AI Integratsiya Dasturchisi",
        company: 'Era AI Platform',
        companyHref: 'https://era2-frontend.vercel.app/',
        period: "2025 – Hozirgacha",
        bullets: [
          "40+ tashqi AI vosita API'sini (REST/JSON) integratsiya qildim va tekshirdim: har bir relizdan oldin Postman va provayder Swagger/OpenAPI hujjatlari bilan ishlab, to'g'ri javoblar, status kodlari va xatolarni qayta ishlash uchun endpointlarni test qildim.",
          "AI bilan tezlashtirilgan QA siklini boshqardim: funksiya spetsifikatsiyalaridan test keyslari, regressiya checklistlari va Playwright to'plamlarini yaratish uchun Claude Code'ga yo'nalish berdim, so'ngra har bir natijani bajardim va qo'lda tekshirdim — ko'p kunlik testlash sikllarini soatlarga siqib.",
          "Vercel joylashtirish va server loglari tahlili orqali ishlab chiqarish hodisalarini aniqladim, Next.js frontend, Node.js API qatlami va PostgreSQL ma'lumotlar bazasi bo'ylab ildiz sabablarini kuzatdim; SQL va Prisma bilan ma'lumotlar yaxlitligini tekshirdim.",
        ],
      },
      {
        role: "Full-Stack Dasturchi",
        company: 'Labour Migration Agency Platform (Specialist Group)',
        companyHref: 'https://labour-agency.vercel.app/',
        period: '2025',
        bullets: [
          "Nomzodlarni qabul qilish shakllari, ro'yxatlar va admin boshqaruv panelini qamrab olgan ishlab chiqarish darajasidagi platformani yetkazib berdim va reliz testidan o'tkazdim — har bir joylashtirishdan oldin ommaviy va administrator rollari bo'ylab boshidan-oxirigacha oqimlarni tekshirib.",
          "PostgreSQL sxemasi va REST API qatlamini loyihalashtirdim; ommaviy shakllar va admin paneli o'rtasidagi ishonchli ma'lumotlar oqimini tekshirish uchun SQL validatsiya so'rovlarini yozdim.",
          "Rolga Asoslangan Kirish Nazoratini joriy qildim va test qildim, reliz tekshiruvi davomida GitHub issue tracking'da nuqsonlarni aniq takrorlash qadamlari bilan hujjatlashtirdim.",
        ],
      },
      {
        role: "AI Ma'lumotlarni Izohlash va Sifat Baholash Bo'yicha Pudratchi",
        company: 'micro1 (Titan Onyx Program, US Company)',
        period: "2026 – Hozirgacha",
        bullets: [
          "LLM natijalarini qat'iy ko'rsatmalarga rioya qilish mezonlariga nisbatan baholadim — qabul qilish testlariga bevosita o'xshash tuzilgan o'tdi/o'tmadi sifat baholashlari — model o'qitish va sifat ko'rsatkichlariga hissa qo'shib.",
          "AQSHlik jamoa uchun ingliz tilida aniq, batafsil baholash asoslarini yozdim, video, audio va matn modalliklari bo'ylab aniq nuqson uslubidagi hisobotlarni qo'lladim.",
        ],
      },
      {
        role: "Frontend Muhandisi",
        company: 'Educational CRM & ERP Platform',
        period: "2025-yil Yanvar – Hozirgacha",
        bullets: [
          "Modulli ERP tizimi uchun qayta ishlatiladigan, TypeScript-birinchi komponentlar kutubxonasini yaratish orqali ishlab chiqish sikli vaqtini 35% ga qisqartirdim.",
          "Ko'p pog'onali Rolga Asoslangan Kirish Nazorati (RBAC) tizimini yaratish va test qilish orqali nozik talaba ma'lumotlarini 3+ ma'muriy kirish darajasi bo'yicha himoyaladim.",
          "Server-side rendering va dinamik kod bo'lish orqali 98/100 unumdorlik balini qo'lga kiritdim; maxsus state-management middleware qatlami bilan UI tezkorligini 50% ga oshirdim.",
        ],
      },
    ],
    education: EDUCATION_STANDARD_UZ,
    certifications: [
      "AI Frontend Engineering Sertifikati — micro1 (AQSH), 2026",
      "Dasturchilar uchun AI va Prompt Engineering — Najot Ta'lim, 2026",
      "Frontend Tizim Arxitekturasi va React Ekotizimi — Najot Ta'lim, 2025",
      "IELTS — 7+ Ball (C1 Ilg'or Ingliz Tili)",
    ],
    languages: LANGUAGES_STANDARD_UZ,
    accent: 'amber',
    icon: 'shield-check',
  },
}

import type { CategoryData, CategoryKey } from '@/lib/resumeData'

const LANGUAGES_STANDARD_RU = [
  { name: 'Узбекский', flag: 'https://flagcdn.com/w80/uz.png', level: 'Родной', fill: 100 },
  { name: 'Английский', flag: 'https://flagcdn.com/w80/gb.png', level: 'Свободно — C1, IELTS 7+ баллов', fill: 90 },
  { name: 'Русский', flag: 'https://flagcdn.com/w80/ru.png', level: 'Разговорный', fill: 45 },
]

const EDUCATION_STANDARD_RU = [
  'Бакалавр по направлению «Управление бизнесом» — Ташкентский государственный экономический университет (обучение продолжается)',
]

export const categories: Record<CategoryKey, CategoryData> = {
  'full-stack': {
    slug: 'full-stack',
    label: 'Full-Stack',
    fullTitle: 'Full-Stack-разработчик',
    tagline: 'Node.js · TypeScript · React 19 · Next.js · Python · .NET · Интеграция ИИ',
    summary: [
      'Full-Stack-разработчик, создающий продакшн веб-приложения от начала до конца — фронтенд на React 19 / Next.js поверх бэкенда на Node.js, Express и PostgreSQL/Prisma — международно сертифицированный как Frontend Engineer Expert от micro1 (США).',
      'Подтверждённые измеримые результаты на пяти работающих платформах (корпоративный ERP, e-commerce, финтех SaaS и ИИ-продукты): 98/100 баллов Lighthouse, на 50% меньше избыточных повторных рендеров и на 40% меньше запросов к серверу. В настоящее время проектирую Era AI — full-stack платформу, объединяющую 40+ ИИ-инструментов и API в едином интерфейсе.',
      'Бэкенд-экспертиза распространяется также на Python (Django, скрипты и автоматизация) и .NET (C# / ASP.NET Core), с типобезопасной архитектурой (дженерики, Zod) и разработкой с применением ИИ (Claude Code, Cursor AI), обеспечивающей до 10x более быстрый релиз.',
    ],
    heroStats: [
      { value: '5+', label: 'Запущенных платформ' },
      { value: '40+', label: 'Интегрированных ИИ-API' },
      { value: '98/100', label: 'Баллов Lighthouse' },
      { value: '10x', label: 'Быстрее с разработкой на базе ИИ' },
    ],
    competencies: [
      { category: 'Языки', items: ['TypeScript (Advanced Generics, Mapped Types, Zod)', 'JavaScript (ES6+/ESNext)', 'Python', 'SQL', 'C# (Working Knowledge)'] },
      { category: 'Backend и API', items: ['Node.js', 'Express', 'REST & GraphQL API Design', 'PostgreSQL', 'Prisma ORM', 'MongoDB', 'Django (Working Knowledge)', '.NET / ASP.NET Core', 'Clerk / NextAuth / JWT'] },
      { category: 'Frontend-разработка', items: ['React 19', 'Next.js (App Router, SSR, Server Actions)', 'Redux Toolkit', 'TanStack Query v5', 'Tailwind CSS'] },
      { category: 'Интеграция ИИ и автоматизация', items: ['OpenAI / Claude / Gemini APIs', 'Prompt Engineering', 'n8n Workflow Automation', 'Claude Code', 'Cursor AI', 'GitHub Copilot'] },
      { category: 'Тестирование и производительность', items: ['Vitest', 'Jest', 'Playwright', 'Core Web Vitals', 'Lighthouse Optimization'] },
      { category: 'Архитектура и DevOps', items: ['RBAC', 'Monorepo (Turborepo)', 'Git/GitHub', 'CI/CD', 'Vercel', 'Docker (Basics)'] },
    ],
    experience: [
      {
        role: 'Full-Stack-инженер и разработчик по интеграции ИИ',
        company: 'Era AI Platform',
        companyHref: 'https://era2-frontend.vercel.app/',
        period: '2026 — настоящее время',
        bullets: [
          'Спроектировал и запустил Era AI — full-stack платформу агрегации ИИ, объединяющую 40+ сторонних ИИ-инструментов и API в едином интерфейсе, построенном на React 19, Next.js и TypeScript.',
          'Единолично отвечаю за весь стек — типобезопасный фронтенд, сервисы на Node.js и слой данных PostgreSQL/Prisma — обеспечивая непрерывное расширение функциональности в продакшене.',
          'Применил prompt engineering для стандартизации и оптимизации ответов от нескольких провайдеров LLM (OpenAI, Claude, Gemini), повысив согласованность ответов для конечных пользователей.',
          'Разработал адаптивный административный интерфейс управления для списка ИИ-инструментов, взаимодействия пользователей и автоматизированных процессов, связывающих системы от начала до конца.',
        ],
      },
      {
        role: 'Подрядчик по оценке ИИ и LLM',
        company: 'micro1 (United States) — Titan Onyx Program',
        period: '2026 — настоящее время',
        bullets: [
          'Оцениваю и калибрую результаты работы нескольких больших языковых моделей по строгим критериям для американской ИИ-компании, напрямую способствуя обучению моделей и повышению эталонных показателей качества.',
          'Получил международно признанную сертификацию Frontend Engineer Expert от micro1 через независимо проведённое тестирование навыков React, TypeScript и проектирования систем.',
        ],
      },
      {
        role: 'Full-Stack-разработчик',
        company: 'Labour Migration Agency Platform (Specialist Group)',
        companyHref: 'https://labour-agency.vercel.app/',
        period: '2026',
        bullets: [
          'Реализовал продакшн-платформу для частного кадрового агентства, включающую формы приёма заявок кандидатов, список вакансий и полноценную административную панель управления.',
          'Спроектировал схему PostgreSQL и слой REST API, связывающий фронтенд на Next.js с бэкенд-сервисами, обеспечив надёжный поток данных между публичными формами и админ-панелью.',
          'Реализовал ролевую модель доступа (RBAC) для чёткого разделения функциональности администратора и соискателя в рамках единой развёрнутой системы.',
        ],
      },
      {
        role: 'Full-Stack Frontend-инженер',
        company: 'Business Finance Manager (SaaS)',
        period: '2026',
        bullets: [
          'Спроектировал типобезопасный финансовый SaaS для бизнеса на TypeScript и Next.js со 100% типобезопасным потоком данных от Prisma до UI, добившись 97/100 баллов Lighthouse.',
          'Разработал дашборд аналитики денежных потоков в реальном времени с оптимистичными обновлениями TanStack Query и автоматической инвалидацией кэша — сократив субъективное время загрузки на 60%.',
          'Разработал высокопроизводительные модули визуализации данных, которые плавно рендерятся на наборах данных свыше 10 000+ финансовых транзакций без задержек интерфейса.',
          'Реализовал сквозную валидацию схем Zod для всех финансовых полей ввода, устранив ошибки времени выполнения на всём жизненном цикле транзакций.',
        ],
      },
      {
        role: 'Frontend-инженер',
        company: 'Educational CRM & ERP Platform',
        period: '2026',
        bullets: [
          'Сократил циклы разработки на 35%, создав переиспользуемую библиотеку компонентов на основе TypeScript и воплотив сложные дизайны из Figma в точный попиксельный адаптивный интерфейс.',
          'Повысил отзывчивость интерфейса на 50% благодаря собственному промежуточному слою управления состоянием, устранившему избыточные повторные рендеры в масштабе корпоративной системы.',
          'Разработал многоуровневую систему RBAC для 3+ административных уровней, обеспечив защиту конфиденциальных данных студентов при сохранении бесшовного и быстрого пользовательского опыта.',
        ],
      },
      {
        role: 'Frontend-разработчик',
        company: 'E-Commerce Storefront (Toshkent Baliqchi)',
        period: '2025',
        bullets: [
          'Развернул высоконагруженную SSR-витрину на Next.js App Router и Tailwind CSS, обеспечив рост SEO-индексации на 25% при переходах между страницами менее чем за секунду.',
          'Переработал глобальное состояние на Redux Toolkit для управления каталогом из 500+ SKU с асинхронными обновлениями без задержек.',
          'Разработал собственный поисковый движок с debounce и систему многокритериальной фильтрации, сократив объём серверных запросов на 40%.',
        ],
      },
    ],
    education: EDUCATION_STANDARD_RU,
    certifications: [
      'Сертификация Frontend Engineer Expert — micro1 (США), 2026 — международно признана, с независимым прокторингом',
      "Программа Frontend Engineering — Najot Ta'lim, 2025 – 2026 — окончена",
      "AI Prompt Engineering (для IT-специалистов) — Najot Ta'lim, 2026 — окончена",
    ],
    languages: LANGUAGES_STANDARD_RU,
    accent: 'sky',
    icon: 'code',
  },

  frontend: {
    slug: 'frontend',
    label: 'Frontend',
    fullTitle: 'Frontend-инженер уровня Expert',
    tagline: 'TypeScript · React 19 · Next.js · Специалист по интеграции ИИ',
    summary: [
      'Frontend-инженер с экспертным владением TypeScript, создающий продакшн-приложения на React 19 и Next.js, международно сертифицированный как Frontend Engineer Expert от micro1 (США).',
      'Подтверждённые измеримые результаты на пяти работающих платформах — корпоративный ERP, e-commerce, финтех SaaS и ИИ-продукты: 98/100 баллов Lighthouse, на 50% меньше избыточных повторных рендеров и на 40% меньше запросов к серверу. В настоящее время проектирую Era AI — full-stack платформу, объединяющую 40+ ИИ-инструментов и API в едином интерфейсе.',
      'Сочетает продвинутую типобезопасную архитектуру (дженерики, mapped types, Zod) с full-stack экспертизой (Node.js, PostgreSQL, Prisma) и разработкой с применением ИИ (Claude Code, Cursor AI), обеспечивающей до 10x более быстрый релиз.',
    ],
    heroStats: [
      { value: '98/100', label: 'Баллов Lighthouse' },
      { value: '50%', label: 'Меньше избыточных повторных рендеров' },
      { value: '40%', label: 'Меньше запросов к серверу' },
      { value: '5', label: 'Запущенных платформ' },
    ],
    competencies: [
      { category: 'TypeScript и JavaScript', items: ['Advanced Generics', 'Mapped & Utility Types', 'Type-Safe API Contracts', 'Zod Schema Validation', 'ES6+/ESNext', 'Functional Programming'] },
      { category: 'Frontend-разработка', items: ['React 19', 'Next.js (App Router, SSR, Server Actions)', 'Redux Toolkit', 'TanStack Query v5', 'Tailwind CSS', 'HTML5/CSS3', 'WCAG Accessibility'] },
      { category: 'Backend и API', items: ['Node.js', 'Express', 'PostgreSQL', 'Prisma ORM', 'REST & GraphQL API Design', 'Clerk / NextAuth'] },
      { category: 'Интеграция ИИ и автоматизация', items: ['OpenAI / Claude / Gemini APIs', 'Prompt Engineering', 'n8n Workflow Automation', 'Claude Code', 'Cursor AI', 'GitHub Copilot'] },
      { category: 'Тестирование и производительность', items: ['Vitest', 'Jest', 'Playwright', 'Core Web Vitals', 'Dynamic Code Splitting', 'Memoization', 'Web Workers'] },
      { category: 'Архитектура и DevOps', items: ['Reusable Component Libraries', 'Atomic Design', 'RBAC', 'Micro-Frontend Patterns', 'Turborepo', 'CI/CD', 'Vercel'] },
    ],
    experience: [
      {
        role: 'Full-Stack-инженер и разработчик по интеграции ИИ',
        company: 'Era AI Platform',
        companyHref: 'https://era2-frontend.vercel.app/',
        period: '2026 — настоящее время',
        bullets: [
          'Спроектировал и запустил Era AI — full-stack платформу агрегации ИИ, объединяющую 40+ сторонних ИИ-инструментов и API в едином интерфейсе, построенном на React 19, Next.js и TypeScript.',
          'Единолично отвечаю за весь стек — типобезопасный фронтенд, сервисы на Node.js и слой данных PostgreSQL/Prisma — обеспечивая непрерывное расширение функциональности в продакшене.',
          'Применил prompt engineering для стандартизации и оптимизации ответов от нескольких провайдеров LLM (OpenAI, Claude, Gemini), повысив согласованность ответов для конечных пользователей.',
          'Разработал адаптивный административный интерфейс управления для списка ИИ-инструментов, взаимодействия пользователей и автоматизированных процессов, связывающих системы от начала до конца.',
        ],
      },
      {
        role: 'Подрядчик по оценке ИИ и LLM',
        company: 'micro1 (United States) — Titan Onyx Program',
        period: '2026 — настоящее время',
        bullets: [
          'Оцениваю и калибрую результаты работы нескольких больших языковых моделей по строгим критериям для американской ИИ-компании, напрямую способствуя обучению моделей и повышению эталонных показателей качества.',
          'Получил международно признанную сертификацию Frontend Engineer Expert от micro1 через независимо проведённое тестирование навыков React, TypeScript и проектирования систем.',
        ],
      },
      {
        role: 'Full-Stack-разработчик',
        company: 'Labour Migration Agency Platform (Specialist Group)',
        companyHref: 'https://labour-agency.vercel.app/',
        period: '2026',
        bullets: [
          'Реализовал продакшн-платформу для частного кадрового агентства, включающую формы приёма заявок кандидатов, список вакансий и полноценную административную панель управления.',
          'Спроектировал схему PostgreSQL и слой REST API, связывающий фронтенд на Next.js с бэкенд-сервисами, обеспечив надёжный поток данных между публичными формами и админ-панелью.',
          'Реализовал ролевую модель доступа (RBAC) для чёткого разделения функциональности администратора и соискателя в рамках единой развёрнутой системы.',
        ],
      },
      {
        role: 'Full-Stack Frontend-инженер',
        company: 'Business Finance Manager (SaaS)',
        period: '2026',
        bullets: [
          'Спроектировал типобезопасный финансовый SaaS для бизнеса на TypeScript и Next.js со 100% типобезопасным потоком данных от Prisma до UI, добившись 97/100 баллов Lighthouse.',
          'Разработал дашборд аналитики денежных потоков в реальном времени с оптимистичными обновлениями TanStack Query и автоматической инвалидацией кэша — сократив субъективное время загрузки на 60%.',
          'Разработал высокопроизводительные модули визуализации данных, которые плавно рендерятся на наборах данных свыше 10 000+ финансовых транзакций без задержек интерфейса.',
        ],
      },
      {
        role: 'Frontend-инженер',
        company: 'Educational CRM & ERP Platform',
        period: '2026',
        bullets: [
          'Сократил циклы разработки на 35%, создав переиспользуемую библиотеку компонентов на основе TypeScript и воплотив сложные дизайны из Figma в точный попиксельный адаптивный интерфейс.',
          'Повысил отзывчивость интерфейса на 50% благодаря собственному промежуточному слою управления состоянием, устранившему избыточные повторные рендеры в масштабе корпоративной системы.',
          'Достиг 98/100 баллов производительности Lighthouse благодаря серверному рендерингу (SSR), динамическому разделению кода и оптимизации CSS/ресурсов.',
        ],
      },
      {
        role: 'Frontend-разработчик',
        company: 'E-Commerce Storefront (Toshkent Baliqchi)',
        period: '2025',
        bullets: [
          'Развернул высоконагруженную SSR-витрину на Next.js App Router и Tailwind CSS, обеспечив рост SEO-индексации на 25% при переходах между страницами менее чем за секунду на всех устройствах.',
          'Переработал глобальное состояние на Redux Toolkit для управления каталогом из 500+ SKU с асинхронными обновлениями без задержек.',
          'Разработал собственный поисковый движок с debounce и систему многокритериальной фильтрации, сократив объём серверных запросов на 40%.',
        ],
      },
    ],
    education: EDUCATION_STANDARD_RU,
    certifications: [
      'Сертификация Frontend Engineer Expert — micro1 (США), 2026 — международно признана, с независимым прокторингом',
      "Программа Frontend Engineering — Najot Ta'lim, 2025 – 2026 — окончена",
      "AI Prompt Engineering (для IT-специалистов) — Najot Ta'lim, 2026 — окончена",
    ],
    languages: LANGUAGES_STANDARD_RU,
    accent: 'violet',
    icon: 'layout',
  },

  'ai-specialist': {
    slug: 'ai-specialist',
    label: 'ИИ-специалист',
    fullTitle: 'Инженер-разработчик ИИ-решений',
    tagline: 'Full-Stack-разработчик · Специалист по Prompt Engineering',
    summary: [
      'Full-Stack инженер-программист с фокусом на ИИ, специализирующийся на интеграции больших языковых моделей (OpenAI, Claude, Gemini, Mistral) в продакшн веб-платформы через prompt engineering и автоматизацию API.',
      'Самостоятельно спроектировал и развернул Era AI — full-stack платформу агрегации ИИ, объединяющую 40+ ИИ-инструментов через API, а также корпоративные приложения на React/Next.js/Node.js с базой данных PostgreSQL.',
      'Сочетает практический опыт оценки ИИ-моделей с родным владением узбекским (C2) и свободным английским (C1, IELTS 7+), что позволяет выступать кросс-функциональным участником команды, готовым создавать платформы на базе ИИ, административные панели и системы автоматизации от концепции до релиза.',
    ],
    heroStats: [
      { value: '40+', label: 'ИИ-инструментов интегрировано через API' },
      { value: '4', label: 'Оркестрируемых провайдеров LLM' },
      { value: '98/100', label: 'Баллов Lighthouse' },
      { value: '1', label: 'Самостоятельно управляемая ИИ-платформа в продакшене' },
    ],
    competencies: [
      { category: 'Инженерия ИИ и LLM', items: ['LLM Integration (OpenAI, Claude, Gemini, Mistral)', 'Prompt Engineering', 'AI Workflow Automation', 'AI Chatbot Development'] },
      { category: 'Backend и автоматизация', items: ['Python (Scripting & Automation)', 'Node.js', 'REST API Design & Integration', 'n8n Workflow Automation'] },
      { category: 'Базы данных', items: ['PostgreSQL', 'MySQL', 'SQL', 'Prisma ORM'] },
      { category: 'Frontend и админ-системы', items: ['React', 'Next.js', 'TypeScript', 'Admin Panel Development'] },
      { category: 'Контроль версий и DevOps', items: ['Git', 'GitHub', 'CI/CD Pipelines', 'Vercel Deployment'] },
    ],
    experience: [
      {
        role: 'Full-Stack инженер по ИИ',
        company: 'Era AI Platform',
        companyHref: 'https://era2-frontend.vercel.app/',
        period: '2026 — настоящее время',
        bullets: [
          'Спроектировал и запустил Era AI, full-stack платформу агрегации ИИ, что выразилось в 40+ интегрированных ИИ-инструментах, доступных из единого интерфейса, за счёт создания фронтенда на React 19/Next.js поверх бэкенда на Node.js с автоматизацией на Python.',
          'Организовал интеграцию нескольких LLM-моделей (OpenAI, Claude, Gemini, Mistral), что выразилось в бесшовном переключении моделей для конечных пользователей, за счёт проектирования переиспользуемых prompt engineering пайплайнов и слоёв абстракции API.',
          'Обеспечил непрерывное единоличное сопровождение платформы, что выразилось в постоянных релизах новых функций после запуска, за счёт самостоятельного управления полным циклом разработки — от архитектуры до развёртывания на Vercel.',
        ],
      },
      {
        role: 'ИИ-тренер и оценщик',
        company: 'micro1 — Titan Onyx Program (U.S.-based)',
        period: '2026',
        bullets: [
          'Оценивал и калибровал результаты работы ИИ-моделей, что выразилось в стабильном соблюдении критериев оценки на сотнях задач, за счёт структурированной аннотации видео/аудио, транскрибирования и ИИ-скрининговых оценок.',
          'Повысил качество ответов моделей, что выразилось в точности калибровки относительно эталонных критериев, за счёт применения экспертизы prompt engineering в модерации контента и процессах оценки качества ответов.',
          'Работал в качестве международного подрядчика для американской компании, специализирующейся на обучении ИИ, получив непосредственный опыт работы с корпоративными стандартами и процессами оценки LLM.',
        ],
      },
      {
        role: 'Full-Stack-инженер',
        company: 'Labour Migration Agency Platform — Specialist Group',
        companyHref: 'https://labour-agency.vercel.app/',
        period: '2025',
        bullets: [
          'Реализовал продакшн веб-платформу Labour Migration и админ-панель, что выразилось в полной передаче проекта клиенту, за счёт создания полного стека на React/Next.js, Node.js и PostgreSQL.',
          'Спроектировал админ-панель для управления делами по миграции, что выразилось в упрощённом вводе и получении данных, за счёт построения реляционной схемы PostgreSQL с эндпоинтами REST API.',
          'Оптимизировал потоки данных между фронтендом и бэкендом, что выразилось в снижении нагрузки от запросов, за счёт внедрения эффективных паттернов интеграции API от начала до конца.',
        ],
      },
      {
        role: 'Frontend-инженер',
        company: 'Educational CRM & ERP Platform',
        period: 'Янв. 2025 — настоящее время',
        bullets: [
          'Сократил циклы разработки на 35%, что выразилось в более быстрой поставке функций, за счёт проектирования переиспользуемой библиотеки компонентов на основе TypeScript для модульной ERP-системы.',
          'Повысил отзывчивость интерфейса на 50%, что выразилось в сокращении избыточных повторных рендеров, за счёт внедрения собственного промежуточного слоя управления состоянием.',
          'Обеспечил защиту конфиденциальных данных студентов на 3+ административных уровнях, что выразилось в отсутствии инцидентов контроля доступа, за счёт разработки многоуровневой системы RBAC с интеграцией REST API.',
        ],
      },
    ],
    education: EDUCATION_STANDARD_RU,
    certifications: [
      'Сертификация AI Frontend Engineering — micro1 (американская компания), 2026',
      "Сертификация Prompt Engineering — Najot Ta'lim, 2025",
      "Архитектура Frontend-систем и экосистема React — Najot Ta'lim, 2025",
      "ИИ и Prompt Engineering для разработчиков — Najot Ta'lim, 2026",
    ],
    languages: LANGUAGES_STANDARD_RU,
    accent: 'fuchsia',
    icon: 'sparkles',
  },

  'qa-tester': {
    slug: 'qa-tester',
    label: 'QA-тестировщик',
    fullTitle: 'Инженер по QA и технической поддержке',
    tagline: 'Тестирование API и веб-приложений · Ускоренный ИИ-процесс (Claude Code)',
    summary: [
      'Инженер с QA-мышлением и full-stack базой: владение REST API, HTTP, JSON, клиент-серверной архитектурой и SQL на уровне разработчика, применяемое в тестировании и диагностике проблем.',
      'Проверил 40+ интеграций сторонних API, создал автоматизированные наборы тестов (Playwright, Vitest, Jest) и проводил структурированные оценки качества для американской компании (micro1).',
      'Использует рабочий процесс с применением ИИ, в котором ~90% рутинных QA- и инженерных задач выполняются через Claude Code по точным промптам, спецификациям и критериям приёмки — каждый результат проверяется лично — обеспечивая качество уровня senior в 10–20 раз быстрее, чем при полностью ручной работе, при этом фокусируясь на исследовательском тестировании, анализе первопричин и общении с клиентами.',
    ],
    heroStats: [
      { value: '40+', label: 'Проверенных сторонних API' },
      { value: '10–20x', label: 'Быстрее благодаря QA на базе ИИ' },
      { value: '3', label: 'Фреймворка автоматизации тестирования' },
      { value: '90%', label: 'Рутинного QA делегировано Claude Code' },
    ],
    competencies: [
      { category: 'QA и тестирование', items: ['Manual Testing (Web & API)', 'Test Cases & Checklists', 'Regression Testing', 'Release Verification', 'Playwright', 'Vitest', 'Jest'] },
      { category: 'Тестирование API', items: ['Postman', 'REST APIs', 'HTTP Protocols', 'JSON', 'Swagger/OpenAPI Documentation'] },
      { category: 'Базы данных', items: ['SQL (PostgreSQL, Prisma ORM)', 'MongoDB (Working Knowledge)'] },
      { category: 'Дефекты и документация', items: ['Bug Reports with Reproduction Steps', 'GitHub Issues (Jira-style Workflow)', 'Technical Documentation', 'Knowledge Base Articles'] },
      { category: 'Диагностика проблем', items: ['Application Log Analysis', 'Root-Cause Analysis', 'Client-Server Architecture', 'Production Debugging (Vercel)'] },
      { category: 'Рабочий процесс с применением ИИ', items: ['Claude Code (Agentic Task Execution)', 'Prompt Engineering', 'OpenAI / Claude / Gemini APIs', 'n8n Automation'] },
      { category: 'Веб-стек', items: ['React 19', 'Next.js', 'TypeScript', 'Node.js', 'Express'] },
    ],
    howIWork: {
      title: 'Как я работаю — разработка с применением ИИ и Claude Code',
      bullets: [
        'Направляю Claude Code с помощью детальных спецификаций, промптов и критериев приёмки для выполнения ~90% рутинной инженерной и QA-работы — генерации тест-кейсов и чек-листов, написания наборов регрессионных тестов, составления баг-репортов и документации, подготовки SQL-запросов для валидации и разбора логов — а затем лично проверяю каждый результат.',
        'Беру на себя уровень принятия решений: исследовательское тестирование, приоритизацию дефектов, анализ первопричин и общение с клиентами. Итог: результат уровня senior на рутинных задачах достигается в 10–20 раз быстрее, сжимая многодневные циклы до часов.',
      ],
    },
    experience: [
      {
        role: 'Full-Stack-инженер и разработчик по интеграции ИИ',
        company: 'Era AI Platform',
        companyHref: 'https://era2-frontend.vercel.app/',
        period: '2025 — настоящее время',
        bullets: [
          'Интегрировал и проверил 40+ API сторонних ИИ-инструментов (REST/JSON): тестировал эндпоинты на корректность ответов, коды статусов и обработку ошибок перед каждым релизом, используя Postman и документацию Swagger/OpenAPI провайдеров.',
          'Проводил ускоренный ИИ-цикл QA: направлял Claude Code на генерацию тест-кейсов, регрессионных чек-листов и наборов Playwright на основе спецификаций функций, затем выполнял и вручную проверял каждый результат — сжимая многодневные циклы тестирования до часов.',
          'Диагностировал инциденты в продакшене через анализ логов развёртывания Vercel и сервера, отслеживая первопричины на уровне фронтенда Next.js, слоя API на Node.js и базы данных PostgreSQL; проверял целостность данных с помощью SQL и Prisma.',
        ],
      },
      {
        role: 'Full-Stack-разработчик',
        company: 'Labour Migration Agency Platform (Specialist Group)',
        companyHref: 'https://labour-agency.vercel.app/',
        period: '2025',
        bullets: [
          'Реализовал и протестировал перед релизом продакшн-платформу, включающую формы приёма заявок кандидатов, списки вакансий и административную панель управления — проверяя сквозные сценарии для публичной и административной ролей перед каждым развёртыванием.',
          'Спроектировал схему PostgreSQL и слой REST API; написал SQL-запросы для валидации надёжного потока данных между публичными формами и админ-панелью.',
          'Реализовал и протестировал ролевую модель доступа (RBAC), документируя дефекты с чёткими шагами воспроизведения в системе отслеживания задач GitHub при проверке релизов.',
        ],
      },
      {
        role: 'Подрядчик по аннотации данных для ИИ и оценке качества',
        company: 'micro1 (Titan Onyx Program, US Company)',
        period: '2026 — настоящее время',
        bullets: [
          'Оценивал результаты работы LLM по строгим критериям соответствия рекомендациям — структурированные оценки качества по принципу pass/fail, напрямую аналогичные приёмочному тестированию — способствуя обучению моделей и формированию эталонных показателей качества.',
          'Составлял чёткие, подробные обоснования оценок на английском языке для американской команды, применяя точную отчётность в стиле баг-репортов для видео, аудио и текстовых форматов.',
        ],
      },
      {
        role: 'Frontend-инженер',
        company: 'Educational CRM & ERP Platform',
        period: 'Янв. 2025 — настоящее время',
        bullets: [
          'Сократил время цикла разработки на 35%, создав переиспользуемую библиотеку компонентов на основе TypeScript для модульной ERP-системы.',
          'Обеспечил защиту конфиденциальных данных студентов на 3+ уровнях административного доступа, разработав и протестировав многоуровневую систему ролевого доступа (RBAC).',
          'Достиг 98/100 баллов производительности благодаря серверному рендерингу и динамическому разделению кода; повысил отзывчивость интерфейса на 50% с помощью собственного промежуточного слоя управления состоянием.',
        ],
      },
    ],
    education: EDUCATION_STANDARD_RU,
    certifications: [
      'Сертификация AI Frontend Engineering — micro1 (США), 2026',
      "ИИ и Prompt Engineering для разработчиков — Najot Ta'lim, 2026",
      "Архитектура Frontend-систем и экосистема React — Najot Ta'lim, 2025",
      'IELTS — 7+ баллов (продвинутый английский C1)',
    ],
    languages: LANGUAGES_STANDARD_RU,
    accent: 'amber',
    icon: 'shield-check',
  },
}

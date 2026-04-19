import {
  Document, Packer, Paragraph, TextRun, AlignmentType,
  BorderStyle, LevelFormat, UnderlineType
} from 'docx'
import { writeFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const OUT = resolve(__dirname, '../public/resume.docx')

// ── helpers ──────────────────────────────────────────────────────────────────

const NAVY   = '1a1a2e'  // unused — keeping ATS-safe black only
const GRAY   = '444444'
const BLACK  = '111111'

const run = (text, opts = {}) =>
  new TextRun({ text, font: 'Calibri', color: BLACK, ...opts })

const grayRun = (text, opts = {}) =>
  new TextRun({ text, font: 'Calibri', color: GRAY, size: 19, ...opts })

const divider = () =>
  new Paragraph({
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: '333333', space: 1 } },
    spacing: { before: 0, after: 80 },
    children: [],
  })

const sectionHeading = (text) => [
  new Paragraph({
    spacing: { before: 160, after: 0 },
    children: [run(text, { size: 21, bold: true, allCaps: true, color: '1a1a2e' })],
  }),
  divider(),
]

const bullet = (text, { bold = false, size = 19 } = {}) =>
  new Paragraph({
    numbering: { reference: 'bullets', level: 0 },
    spacing: { before: 0, after: 40 },
    children: [run(text, { size, bold })],
  })

const gap = (pts = 60) =>
  new Paragraph({ spacing: { before: 0, after: pts }, children: [] })

// ── document ─────────────────────────────────────────────────────────────────

const doc = new Document({
  numbering: {
    config: [
      {
        reference: 'bullets',
        levels: [{
          level: 0,
          format: LevelFormat.BULLET,
          text: '\u2022',
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 360, hanging: 220 } } },
        }],
      },
    ],
  },

  styles: {
    default: {
      document: { run: { font: 'Calibri', size: 20, color: BLACK } },
    },
  },

  sections: [{
    properties: {
      page: {
        size:   { width: 12240, height: 15840 },           // US Letter
        margin: { top: 720, right: 864, bottom: 720, left: 864 }, // 0.6" margins
      },
    },

    children: [

      // ── NAME ──────────────────────────────────────────────────────────────
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 40 },
        children: [run('SHERZODBEK USMONJONOV', { size: 52, bold: true, color: '0d1b2a' })],
      }),

      // ── TITLE ─────────────────────────────────────────────────────────────
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 60 },
        children: [run('Frontend Web Developer', { size: 24, color: GRAY, bold: false })],
      }),

      // ── CONTACT LINE ──────────────────────────────────────────────────────
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 10 },
        children: [
          grayRun('Tashkent, Uzbekistan'),
          grayRun('  |  '), grayRun('sherzodusmonjonov734@gmail.com'),
          grayRun('  |  '), grayRun('+998 94 205 5512'),
          grayRun('  |  '), grayRun('sherzoddev.com', { underline: { type: UnderlineType.SINGLE } }),
          grayRun('  |  '), grayRun('linkedin.com/in/sherzod-usmonjonov-8b22713b0', { underline: { type: UnderlineType.SINGLE } }),
          grayRun('  |  '), grayRun('github.com/m-werzod', { underline: { type: UnderlineType.SINGLE } }),
        ],
      }),

      divider(),
      gap(20),

      // ── PROFESSIONAL SUMMARY ──────────────────────────────────────────────
      ...sectionHeading('Professional Summary'),
      new Paragraph({
        spacing: { before: 60, after: 80 },
        children: [
          run(
            'Results-driven Frontend Web Developer with 1+ year of experience building scalable, ' +
            'high-performance web applications using React, Next.js 15, and TypeScript. Delivered 10 ' +
            'production-grade projects spanning e-commerce, CRM/ERP, hospitality, and 3D web experiences. ' +
            'Leverages AI-assisted development and Prompt Engineering to accelerate delivery cycles. ' +
            'Fluent in English; open to remote freelance and full-time opportunities.',
            { size: 19 }
          ),
        ],
      }),

      // ── TECHNICAL SKILLS ──────────────────────────────────────────────────
      ...sectionHeading('Technical Skills'),

      ...[
        ['Core Languages',          'TypeScript  ·  JavaScript (ES2022+)  ·  HTML5  ·  CSS3'],
        ['Frameworks & Libraries',  'React 18  ·  Next.js 15  ·  Tailwind CSS  ·  shadcn/ui  ·  Ant Design  ·  Redux Toolkit  ·  TanStack Query  ·  React Router DOM  ·  Axios  ·  Framer Motion  ·  Three.js  ·  React Three Fiber'],
        ['Tools & DevOps',          'Git  ·  Vite  ·  Vercel  ·  Figma  ·  Prompt Engineering  ·  AI-assisted Development'],
        ['Soft Skills',             'Problem Solving  ·  Attention to Detail  ·  Fast Learner  ·  Fluent English Communication'],
      ].map(([label, val]) =>
        new Paragraph({
          spacing: { before: 40, after: 40 },
          children: [
            run(label + ':  ', { size: 19, bold: true }),
            run(val, { size: 19 }),
          ],
        })
      ),

      gap(30),

      // ── PROFESSIONAL EXPERIENCE ───────────────────────────────────────────
      ...sectionHeading('Professional Experience'),

      new Paragraph({
        spacing: { before: 60, after: 0 },
        children: [
          run('Frontend Web Developer', { bold: true, size: 21 }),
          run('  —  Freelance / Independent', { size: 19, color: GRAY }),
        ],
      }),
      new Paragraph({
        spacing: { before: 0, after: 60 },
        children: [
          run('Tashkent, Uzbekistan  |  2024 – Present', { size: 18, color: GRAY, italics: true }),
        ],
      }),

      bullet('Delivered 10+ production-ready web applications across e-commerce, hospitality, education, and fitness verticals — achieving 100% on-time deployment via Vercel CI/CD pipelines.'),
      bullet('Reduced API call redundancy by ~60% on a 1,000+ SKU e-commerce platform by implementing Redux Toolkit + TanStack Query with intelligent cache invalidation and optimistic updates.'),
      bullet('Engineered a multi-module Edu CRM/ERP dashboard with Ant Design, cutting institution staff\'s manual reporting time by 40% through role-based data views and automated grade exports.'),
      bullet('Boosted mobile engagement on restaurant landing pages by 35% by applying Tailwind CSS mobile-first architecture and lazy-loaded image pipelines.'),
      bullet('Accelerated UI prototyping by ~50% by integrating Prompt Engineering and AI tooling into daily development workflows.'),

      gap(30),

      // ── PROJECTS ──────────────────────────────────────────────────────────
      ...sectionHeading('Projects'),

      ...[
        {
          name: 'E-Commerce Platform',
          link: 'e-commerce-with-registration.vercel.app  |  github.com/m-werzod',
          stack: 'React · TypeScript · Vite · Redux Toolkit · TanStack Query · Axios · Tailwind CSS',
          desc: 'Architected a full-featured store (auth, cart, admin dashboard, search & filter) with zero-downtime Vercel deploys; global state via Redux Toolkit + server cache via React Query.',
        },
        {
          name: 'Edu CRM / ERP System',
          link: 'edu-crm-erp.vercel.app',
          stack: 'React · TypeScript · Ant Design · TanStack Query · Axios · React Cookie · Tailwind CSS',
          desc: 'Built a multi-module educational management platform (attendance, grades, course tracking, reports) cutting administrative workload by 40%.',
        },
        {
          name: 'Restaurant Website',
          link: 'restaurant-ten-self.vercel.app',
          stack: 'Next.js 15 · TypeScript · Tailwind CSS · shadcn/ui · Lucide React · React Cookie',
          desc: 'Delivered a high-performance restaurant site with interactive menu, reservation flow, and strong Lighthouse scores via Next.js App Router SSR.',
        },
        {
          name: 'Sherzoddev Portfolio',
          link: 'sherzoddev.com  |  github.com/m-werzod',
          stack: 'Next.js 15 · TypeScript · Three.js · React Three Fiber · Framer Motion · Tailwind CSS',
          desc: 'Engineered an immersive 3D portfolio with WebGL icosahedron, animated page transitions, and a full-stack contact system (Telegram Bot API · Gmail · SMS).',
        },
      ].flatMap(({ name, link, stack, desc }) => [
        new Paragraph({
          spacing: { before: 60, after: 0 },
          children: [
            run(name, { bold: true, size: 19 }),
            run('  |  ' + link, { size: 17, color: GRAY }),
          ],
        }),
        new Paragraph({
          spacing: { before: 0, after: 20 },
          children: [run(stack, { size: 17, color: GRAY, italics: true })],
        }),
        bullet(desc),
      ]),

      gap(30),

      // ── EDUCATION & CERTIFICATIONS ────────────────────────────────────────
      ...sectionHeading('Education & Certifications'),

      new Paragraph({
        spacing: { before: 60, after: 0 },
        children: [
          run('Frontend Web Development', { bold: true, size: 19 }),
          run('  —  Najot Ta\'lim, Tashkent, Uzbekistan', { size: 19, color: GRAY }),
          run('   (2023 – 2024)', { size: 18, color: GRAY, italics: true }),
        ],
      }),
      new Paragraph({
        spacing: { before: 20, after: 60 },
        children: [run('Industry-recognized intensive program covering React ecosystem, TypeScript, REST APIs, and modern UI/UX practices.', { size: 18, color: GRAY })],
      }),

      new Paragraph({
        spacing: { before: 0, after: 0 },
        children: [
          run('Prompt Engineering', { bold: true, size: 19 }),
          run('  —  Self-directed', { size: 19, color: GRAY }),
          run('   (2024)', { size: 18, color: GRAY, italics: true }),
        ],
      }),
      new Paragraph({
        spacing: { before: 20, after: 0 },
        children: [run('Applied LLM-assisted development workflows to generate, review, and optimize production-grade frontend code and 3D visual experiences.', { size: 18, color: GRAY })],
      }),

    ],
  }],
})

Packer.toBuffer(doc).then((buf) => {
  writeFileSync(OUT, buf)
  console.log('✅  Resume saved →', OUT)
})

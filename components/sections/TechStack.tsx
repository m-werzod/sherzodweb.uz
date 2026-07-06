'use client'
import { motion } from 'framer-motion'

const DEVICON = 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons'
const SIMPLE  = 'https://cdn.simpleicons.org'

// ── Row 1 — Frontend / UI (left → right) ────────────────────────────────────
const row1Techs = [
  { name: 'HTML5',         icon: `${DEVICON}/html5/html5-original.svg`                  },
  { name: 'CSS3',          icon: `${DEVICON}/css3/css3-original.svg`                    },
  { name: 'JavaScript',    icon: `${DEVICON}/javascript/javascript-original.svg`         },
  { name: 'TypeScript',    icon: `${DEVICON}/typescript/typescript-original.svg`         },
  { name: 'React',         icon: `${DEVICON}/react/react-original.svg`                  },
  { name: 'Next.js',       icon: `${DEVICON}/nextjs/nextjs-original.svg`                },
  { name: 'Tailwind CSS',  icon: `${DEVICON}/tailwindcss/tailwindcss-original.svg`      },
  { name: 'Framer Motion', icon: `${SIMPLE}/framer/white`                               },
  { name: 'Three.js',      icon: `${DEVICON}/threejs/threejs-original.svg`              },
  { name: 'Vite',          icon: `${DEVICON}/vite/vite-original.svg`                    },
  { name: 'Figma',         icon: `${DEVICON}/figma/figma-original.svg`                  },
  { name: 'Sass',          icon: `${DEVICON}/sass/sass-original.svg`                    },
]

// ── Row 2 — Backend / Tools / AI / QA (right → left) ──────────────────────────
const row2Techs = [
  { name: 'Node.js',         icon: `${DEVICON}/nodejs/nodejs-original.svg`              },
  { name: '.NET',            icon: `${DEVICON}/dot-net/dot-net-original.svg`            },
  { name: 'Python',          icon: `${DEVICON}/python/python-original.svg`              },
  { name: 'Redux',           icon: `${DEVICON}/redux/redux-original.svg`                },
  { name: 'Git',             icon: `${DEVICON}/git/git-original.svg`                    },
  { name: 'PostgreSQL',      icon: `${DEVICON}/postgresql/postgresql-original.svg`      },
  { name: 'AI Integration',  icon: 'https://img.icons8.com/color/96/chatgpt.png'        },
  { name: 'Automations',     icon: `${SIMPLE}/n8n/EA4B71`                              },
  { name: 'Playwright',      icon: `${DEVICON}/playwright/playwright-original.svg`      },
  { name: 'Postman',         icon: `${DEVICON}/postman/postman-original.svg`            },
  { name: 'Jest',            icon: `${DEVICON}/jest/jest-plain.svg`                     },
  { name: 'Vercel',          icon: `${SIMPLE}/vercel/white`                             },
  { name: 'Ant Design',      icon: `${DEVICON}/antdesign/antdesign-original.svg`        },
  { name: 'Axios',           icon: `${DEVICON}/axios/axios-plain-wordmark.svg`          },
  { name: 'React Query',     icon: `${SIMPLE}/reactquery/FF4154`                        },
  { name: 'shadcn/ui',       icon: `${SIMPLE}/shadcnui/white`                           },
  { name: 'Prompt Eng.',     icon: `${SIMPLE}/anthropic/white`                          },
]

// Doubled for seamless infinite loop
const topRow    = [...row1Techs, ...row1Techs]
const bottomRow = [...row2Techs, ...row2Techs]

type Tech = { name: string; icon: string }

function TechPill({ tech }: { tech: Tech }) {
  return (
    <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-full border border-white/10 bg-white/[0.03] text-sm font-semibold shrink-0 hover:scale-105 hover:border-[#38bdf8]/30 hover:bg-[#38bdf8]/5 transition-all duration-200 cursor-default select-none">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={tech.icon}
        alt={tech.name}
        width={20}
        height={20}
        loading="eager"
        decoding="async"
        className="w-5 h-5 object-contain shrink-0"
      />
      <span className="text-slate-300 whitespace-nowrap">{tech.name}</span>
    </div>
  )
}

const MASK = '[mask-image:linear-gradient(to_right,transparent,black_6%,black_94%,transparent)]'

export default function TechStack() {
  return (
    <section id="tech-stack" className="py-24 overflow-hidden relative">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-sky-950/5 to-transparent pointer-events-none" />

      {/* Heading */}
      <div className="max-w-7xl mx-auto px-6 mb-12 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
        >
          <p className="text-xs text-[#38bdf8] font-semibold tracking-[0.25em] uppercase mb-3">Tech Arsenal</p>
          <h2 className="text-3xl md:text-4xl font-black text-white">
            Technologies I <span className="text-[#38bdf8]">Master</span>
          </h2>
          <p className="text-slate-500 text-sm mt-2">Frontend · Backend · AI &amp; Automation</p>
        </motion.div>
      </div>

      {/* Row 1 — Frontend chain → */}
      <div className={`relative mb-4 ${MASK}`}>
        <div
          className="flex gap-3 marquee-row1"
          style={{ willChange: 'transform', transform: 'translateZ(0)' }}
        >
          {topRow.map((tech, i) => <TechPill key={`r1-${i}`} tech={tech} />)}
        </div>
      </div>

      {/* Row 2 — Backend/AI/Tools chain ← */}
      <div className={`relative ${MASK}`}>
        <div
          className="flex gap-3 marquee-row2"
          style={{ willChange: 'transform', transform: 'translateZ(0)' }}
        >
          {bottomRow.map((tech, i) => <TechPill key={`r2-${i}`} tech={tech} />)}
        </div>
      </div>
    </section>
  )
}

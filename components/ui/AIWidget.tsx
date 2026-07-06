'use client'
import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

// Modern professional AI sparkle icon (Claude/Gemini style)
const BotIcon = ({ className = 'w-6 h-6' }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    {/* Primary 4-point sparkle */}
    <path d="M10.5 2a.6.6 0 01.58.44l1.18 4.13c.3 1.04 1.13 1.87 2.17 2.17l4.13 1.18a.6.6 0 010 1.16l-4.13 1.18c-1.04.3-1.87 1.13-2.17 2.17l-1.18 4.13a.6.6 0 01-1.16 0L8.74 13.4c-.3-1.04-1.13-1.87-2.17-2.17L2.44 10.05a.6.6 0 010-1.16l4.13-1.18c1.04-.3 1.87-1.13 2.17-2.17l1.18-4.13A.6.6 0 0110.5 2z"/>
    {/* Smaller accent sparkle */}
    <path d="M18.5 13.5a.4.4 0 01.39.3l.5 1.74c.13.44.48.79.92.92l1.74.5a.4.4 0 010 .78l-1.74.5c-.44.13-.79.48-.92.92l-.5 1.74a.4.4 0 01-.78 0l-.5-1.74a1.3 1.3 0 00-.92-.92l-1.74-.5a.4.4 0 010-.78l1.74-.5c.44-.13.79-.48.92-.92l.5-1.74a.4.4 0 01.39-.3z"/>
  </svg>
)

// One-shot send chime using Web Audio API (no external files)
let audioCtx: AudioContext | null = null
function playSendSound() {
  if (typeof window === 'undefined') return
  try {
    if (!audioCtx) {
      const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      audioCtx = new Ctx()
    }
    const ctx = audioCtx
    const fire = () => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain); gain.connect(ctx.destination)
      const now = ctx.currentTime + 0.002
      osc.type = 'sine'
      osc.frequency.setValueAtTime(520, now)
      osc.frequency.exponentialRampToValueAtTime(880, now + 0.12)
      gain.gain.setValueAtTime(0.0001, now)
      gain.gain.exponentialRampToValueAtTime(0.35, now + 0.01)
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.2)
      osc.start(now); osc.stop(now + 0.22)
    }
    if (ctx.state === 'suspended') ctx.resume().then(fire).catch(() => {})
    else fire()
  } catch {}
}

type Tab = 'Tech Stack' | 'Specializations' | 'Projects' | 'Contact Info' | 'About Me'

const knowledge: Record<Tab, { q: string; a: string }> = {
  'Tech Stack': {
    q: 'What technologies does Sherzod use?',
    a: 'Sherzod\'s stack spans the full lifecycle:\n\nFrontend: React 19, Next.js 15 (App Router), TypeScript, Tailwind CSS, Redux Toolkit, TanStack Query, Framer Motion, Three.js / React Three Fiber\n\nBackend: Node.js, Express, PostgreSQL, Prisma ORM, REST & GraphQL APIs, Python (Django), .NET / C# (ASP.NET Core)\n\nAI Integration: OpenAI, Claude & Gemini APIs, Prompt Engineering, n8n automation, Claude Code, Cursor AI\n\nQA & Testing: Playwright, Vitest, Jest, Postman, SQL validation, Core Web Vitals / Lighthouse\n\nTooling: Git/GitHub, Figma, Vercel, Docker basics, CI/CD, RBAC & auth (Clerk/NextAuth/JWT)',
  },
  Specializations: {
    q: 'What does Sherzod specialize in?',
    a: 'Sherzod works across four specializations — each has its own dedicated page on this site:\n\n1. Full Stack — end-to-end platforms: React/Next.js frontends on Node.js, PostgreSQL/Prisma, plus Python and .NET on the backend.\n2. Frontend — TypeScript-expert UI engineering, internationally certified Frontend Engineer Expert by micro1 (US).\n3. AI Specialist — LLM integration & prompt engineering, orchestrating 40+ AI tools/APIs (OpenAI, Claude, Gemini) in production.\n4. QA Tester — API & release testing (Playwright, Vitest, Jest, Postman), with an AI-augmented workflow (Claude Code) that runs QA 10–20x faster.\n\nVisit /full-stack, /frontend, /ai-specialist or /qa-tester to see the tailored experience, projects, and case for each.',
  },
  Projects: {
    q: 'What projects has Sherzod built?',
    a: 'Sherzod has shipped 13 real-world projects. Flagship platforms:\n\n1. Era AI Platform — full-stack AI aggregation product integrating 40+ AI tools (OpenAI, Claude, Gemini) behind one interface — React 19, Next.js, Node.js, PostgreSQL/Prisma\n2. Labour Migration Agency Platform — production employment platform with candidate intake, vacancy listings, admin panel & RBAC — React, Next.js, Node.js, PostgreSQL\n\nPlus (Featured): E-Commerce Platform, Restaurant Website, Edu CRM/ERP System, Business Finance Manager.\n\nMore Work: Toshkent Baliqchi, Nexora Labs, iPhone Store UZ, Fitness Time Gym, Parfume Market, Barakah Restaurant, and this Sherzoddev Portfolio itself.\n\nSee them all — with live demos — on the Projects page!',
  },
  'Contact Info': {
    q: 'How can I contact Sherzod?',
    a: 'You can reach Sherzod via:\nEmail: sherzodusmonjonov734@gmail.com\nPhone: +998 94 205 5512\nTelegram: @WerzodUsmanov\nGitHub: github.com/m-werzod\nLinkedIn: /in/sherzod-usmonjonov-8b22713b0\nInstagram: @Sherzod_usmanovv\n\nHe is currently available for freelance and full-time opportunities, and typically responds within 24 hours!',
  },
  'About Me': {
    q: 'Tell me about Sherzod.',
    a: 'Sherzodbek Usmonjonov is a Full-Stack Engineer & AI Integration Specialist from Uzbekistan with 3+ years of experience, internationally certified as a Frontend Engineer Expert by micro1 (United States).\n\nHe\'s solo-architected Era AI (40+ integrated AI tools) and shipped the Labour Migration Agency platform, alongside enterprise ERP, e-commerce and fintech SaaS products — with results like 98/100 Lighthouse scores and 50% fewer redundant re-renders.\n\nEducation: Bachelor of Business Management, Tashkent State University of Economics (in progress); graduate of Najot Ta\'lim\'s Frontend Engineering and AI Prompt Engineering programs.\n\nLanguages: Uzbek (Native) · English (Fluent, C1/IELTS 7+) · Russian (Conversational)\n\nAvailable for freelance and full-time work!',
  },
}

function smartReply(input: string): string {
  const q = input.toLowerCase()
  if (/contact|email|phone|telegram|reach|message|dm|whatsapp|call|instagram|linkedin/.test(q)) return knowledge['Contact Info'].a
  if (/project|built|work|portfolio|app|site|website|ecommerce|restaurant|finance|crm|erp|gym|parfume|baliqchi|nexora|iphone|era ai|labour|migration/.test(q)) return knowledge['Projects'].a
  if (/full[\s-]?stack|frontend|front-end|ai specialist|qa|q\.a\.|quality assurance|tester|specializ/.test(q)) return knowledge['Specializations'].a
  if (/tech|stack|technology|language|framework|react|next|typescript|tailwind|three\.?js|figma|node|git|tools|\.net|dotnet|python|playwright|jest|vitest|postman/.test(q)) return knowledge['Tech Stack'].a
  if (/educat|school|study|najot|degree|certif|prompt|ai|artificial|who|about|sherzod|himself|bio|background|experience|uzbek|developer|years/.test(q)) return knowledge['About Me'].a
  if (/hire|available|freelance|job|opportunity|work together|collaborate|price|cost|rate/.test(q))
    return "Sherzod is currently available for freelance projects and full-time opportunities!\n\nBest way to reach him:\nTelegram: @WerzodUsmanov\nEmail: sherzodusmonjonov734@gmail.com\n\nHe typically responds within 24 hours."
  if (/hello|hi |hey|sup|what's up|yo |greet/.test(q))
    return "Hey there! I'm Sherzod's AI assistant. I can tell you about his projects, specializations, tech stack, experience, or how to get in touch. What would you like to know?"
  if (/salary|pay|rate|cost|price|budget/.test(q))
    return "For project pricing or salary expectations, it's best to discuss directly with Sherzod.\n\nTelegram: @WerzodUsmanov\nEmail: sherzodusmonjonov734@gmail.com\n\nHe'll get back to you quickly!"
  return "Great question! I have info about Sherzod's projects, specializations (Full Stack, Frontend, AI, QA), tech stack, experience, and contact details. Try the quick tabs above or ask something like:\n• \"What projects has he built?\"\n• \"What does he specialize in?\"\n• \"How can I contact him?\""
}

interface Message { role: 'user' | 'assistant'; content: string }

const bubbleMessages = [
  "Hi! Ask me about Sherzod",
  "See his 13 projects!",
  "Available for hire!",
  "Ask about his specializations",
]

export default function AIWidget() {
  const [open, setOpen]           = useState(false)
  const [bubble, setBubble]       = useState(true)
  const [bubbleIdx, setBubbleIdx] = useState(0)
  const [messages, setMessages]   = useState<Message[]>([
    { role: 'assistant', content: "Hi! I'm Sherzod's AI assistant. Ask me anything about his skills, projects, or how to get in touch!" },
  ])
  const [input, setInput]         = useState('')
  const [thinking, setThinking]   = useState(false)
  const [streaming, setStreaming] = useState(false)

  const messagesEndRef   = useRef<HTMLDivElement>(null)
  const streamTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking])

  // Rotate bubble message every 4 s
  useEffect(() => {
    if (!bubble || open) return
    const id = setInterval(() => setBubbleIdx((i) => (i + 1) % bubbleMessages.length), 4000)
    return () => clearInterval(id)
  }, [bubble, open])

  // Hide bubble after 18 s
  useEffect(() => {
    const id = setTimeout(() => setBubble(false), 18000)
    return () => clearTimeout(id)
  }, [])

  // Cancel any in-flight stream on unmount
  useEffect(() => () => {
    if (streamTimeoutRef.current) clearTimeout(streamTimeoutRef.current)
  }, [])

  // ── Stream a reply character-by-character (silent) ────────────────────────
  const streamReply = useCallback((text: string) => {
    setThinking(true)
    setStreaming(false)
    const thinkDelay = 450 + Math.random() * 350

    streamTimeoutRef.current = setTimeout(() => {
      setThinking(false)
      setStreaming(true)
      setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

      let i = 0
      const step = () => {
        if (i >= text.length) {
          setStreaming(false)
          return
        }
        const chunk = Math.random() < 0.25 ? 2 : 1
        i = Math.min(text.length, i + chunk)
        const slice = text.slice(0, i)
        setMessages((prev) => {
          const next = prev.slice()
          next[next.length - 1] = { role: 'assistant', content: slice }
          return next
        })
        const lastChar = text[i - 1]
        const delay =
          lastChar === '\n' ? 140 :
          /[.!?]/.test(lastChar) ? 200 :
          /[,;:]/.test(lastChar) ? 100 :
          20 + Math.random() * 25
        streamTimeoutRef.current = setTimeout(step, delay)
      }
      step()
    }, thinkDelay)
  }, [])

  const openChat = () => { setOpen(true); setBubble(false) }

  const handleTab = (tab: Tab) => {
    if (thinking || streaming) return
    const { q, a } = knowledge[tab]
    setMessages((prev) => [...prev, { role: 'user', content: q }])
    streamReply(a)
  }

  const handleSend = () => {
    if (!input.trim() || thinking || streaming) return
    const userMsg = input.trim()
    playSendSound()
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }])
    setInput('')
    streamReply(smartReply(userMsg))
  }

  const statusText = thinking || streaming ? 'typing…' : 'Online — Ask about Sherzod'

  return (
    <>
      {/* ── Speech bubble ──────────────────────────────────────────────────── */}
      <AnimatePresence>
        {bubble && !open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.7, y: 12, x: 8 }}
            animate={{ opacity: 1, scale: 1,   y: 0,  x: 0 }}
            exit={{   opacity: 0, scale: 0.7, y: 12, x: 8 }}
            transition={{ type: 'spring', stiffness: 320, damping: 22 }}
            className="fixed bottom-[88px] right-6 z-50 max-w-[210px] cursor-pointer select-none"
            onClick={openChat}
          >
            <div className="relative bg-white text-[#0a0f1e] text-xs font-semibold px-4 py-2.5 rounded-2xl shadow-xl shadow-black/30 leading-snug">
              <AnimatePresence mode="wait">
                <motion.span
                  key={bubbleIdx}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{   opacity: 0, y: -4 }}
                  transition={{ duration: 0.3 }}
                  className="block"
                >
                  {bubbleMessages[bubbleIdx]}
                </motion.span>
              </AnimatePresence>
              <button
                onClick={(e) => { e.stopPropagation(); setBubble(false) }}
                className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-slate-400 hover:bg-slate-500 text-white flex items-center justify-center text-[9px] leading-none transition-colors"
              >
                ✕
              </button>
              <span className="absolute -bottom-2 right-5 w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-t-[8px] border-t-white" />
            </div>
            <motion.div
              className="absolute inset-0 rounded-2xl ring-2 ring-white/30"
              animate={{ scale: [1, 1.06, 1], opacity: [0.6, 0, 0.6] }}
              transition={{ duration: 2.5, repeat: Infinity }}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Toggle button ───────────────────────────────────────────────────── */}
      <motion.button
        onClick={() => (open ? setOpen(false) : openChat())}
        whileHover={{ scale: 1.08 }}
        whileTap={{ scale: 0.93 }}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-2xl bg-gradient-to-br from-sky-500 to-blue-700 shadow-lg shadow-sky-900/50 flex items-center justify-center overflow-hidden"
        aria-label="AI Assistant"
      >
        <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.3 }}>
          {open ? (
            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          ) : (
            <BotIcon className="w-7 h-7 text-white" />
          )}
        </motion.div>

        {bubble && !open && (
          <span className="absolute top-1 right-1 w-2.5 h-2.5 rounded-full bg-emerald-400 border-2 border-blue-700">
            <motion.span
              className="absolute inset-0 rounded-full bg-emerald-400"
              animate={{ scale: [1, 1.8], opacity: [0.8, 0] }}
              transition={{ duration: 1.2, repeat: Infinity }}
            />
          </span>
        )}
        {!open && (
          <motion.span
            className="absolute inset-0 rounded-2xl border-2 border-sky-400"
            animate={{ scale: [1, 1.45], opacity: [0.6, 0] }}
            transition={{ duration: 1.8, repeat: Infinity }}
          />
        )}
      </motion.button>

      {/* ── Chat panel ──────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.94 }}
            animate={{ opacity: 1, y: 0,  scale: 1    }}
            exit={{   opacity: 0, y: 24, scale: 0.94 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className="fixed bottom-24 right-6 z-50 w-80 md:w-96 rounded-2xl border border-white/10 bg-[#0a1628]/95 backdrop-blur-xl shadow-2xl shadow-sky-950/50 overflow-hidden"
          >
            {/* Header with live status */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-white/10 bg-gradient-to-r from-sky-950/50 to-transparent">
              <BotIcon className="w-8 h-8 text-[#38bdf8]" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-bold text-white">AI Assistant</p>
                <div className="flex items-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${thinking || streaming ? 'bg-[#38bdf8]' : 'bg-emerald-400'} animate-pulse`} />
                  <AnimatePresence mode="wait">
                    <motion.p
                      key={statusText}
                      initial={{ opacity: 0, y: 3 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -3 }}
                      transition={{ duration: 0.18 }}
                      className={`text-xs truncate ${thinking || streaming ? 'text-[#38bdf8]' : 'text-slate-400'}`}
                    >
                      {statusText}
                      {(thinking || streaming) && (
                        <span className="inline-flex ml-1 gap-0.5">
                          {[0, 0.15, 0.3].map((d, i) => (
                            <motion.span key={i} className="w-1 h-1 rounded-full bg-[#38bdf8]"
                              animate={{ y: [0, -2, 0] }} transition={{ duration: 0.7, repeat: Infinity, delay: d }} />
                          ))}
                        </span>
                      )}
                    </motion.p>
                  </AnimatePresence>
                </div>
              </div>
              <button
                onClick={() => {
                  if (streamTimeoutRef.current) clearTimeout(streamTimeoutRef.current)
                  setThinking(false); setStreaming(false)
                  setMessages([{ role: 'assistant', content: "Hi! I'm Sherzod's AI assistant. Ask me anything about his skills, projects, or how to get in touch!" }])
                }}
                className="text-[10px] text-slate-600 hover:text-slate-400 transition-colors px-2 py-1 rounded-lg hover:bg-white/5"
                title="Clear chat"
              >
                Clear
              </button>
            </div>

            {/* Quick-topic tabs */}
            <div className="flex gap-1.5 p-3 overflow-x-auto border-b border-white/5 bg-black/10 scrollbar-none">
              {(Object.keys(knowledge) as Tab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => handleTab(tab)}
                  disabled={thinking || streaming}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white/5 hover:bg-[#38bdf8]/15 hover:text-[#38bdf8] text-slate-400 border border-white/5 hover:border-[#38bdf8]/30 transition-all whitespace-nowrap shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Messages */}
            <div className="h-64 overflow-y-auto p-4 flex flex-col gap-3">
              {messages.map((msg, i) => {
                const isLast = i === messages.length - 1
                const showCaret = isLast && msg.role === 'assistant' && streaming
                return (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    {msg.role === 'assistant' && (
                      <BotIcon className="w-5 h-5 text-[#38bdf8] self-end mb-0.5 mr-1.5 shrink-0" />
                    )}
                    <div
                      className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed whitespace-pre-line ${
                        msg.role === 'user'
                          ? 'bg-[#38bdf8] text-[#020617] font-medium rounded-tr-sm'
                          : 'bg-white/5 text-slate-300 border border-white/5 rounded-tl-sm'
                      }`}
                    >
                      {msg.content}
                      {showCaret && (
                        <motion.span
                          className="inline-block w-[2px] h-3 align-middle ml-0.5 bg-[#38bdf8]"
                          animate={{ opacity: [1, 0, 1] }}
                          transition={{ duration: 0.7, repeat: Infinity }}
                        />
                      )}
                    </div>
                  </motion.div>
                )
              })}

              {thinking && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start items-end gap-1.5">
                  <BotIcon className="w-5 h-5 text-[#38bdf8] shrink-0" />
                  <div className="bg-white/5 border border-white/5 rounded-2xl rounded-tl-sm px-4 py-3 flex gap-1">
                    {[0, 0.15, 0.3].map((d, i) => (
                      <motion.span key={i} className="w-1.5 h-1.5 rounded-full bg-slate-400"
                        animate={{ y: [0, -4, 0] }} transition={{ duration: 0.6, repeat: Infinity, delay: d }} />
                    ))}
                  </div>
                </motion.div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="flex items-center gap-2 p-3 border-t border-white/5">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                placeholder="Ask anything about Sherzod…"
                className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-[#38bdf8]/40 transition-colors"
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || thinking || streaming}
                className="w-8 h-8 rounded-xl bg-[#38bdf8] flex items-center justify-center hover:bg-sky-300 transition-colors shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <svg className="w-3.5 h-3.5 text-[#020617]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

'use client'
import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

type Tab = 'Tech Stack' | 'Projects' | 'Contact Info' | 'About Me' | 'Education & AI'

const knowledge: Record<Tab, { q: string; a: string }> = {
  'Tech Stack': {
    q: 'What technologies does Sherzod use?',
    a: 'Sherzod specializes in React, Next.js 15, TypeScript, and Tailwind CSS. He creates motion designs with Framer Motion, builds 3D web experiences using Three.js / React Three Fiber, and integrates AI tools into his workflow. His toolbox also includes Node.js, Git, Figma, and Vercel for deployment.',
  },
  Projects: {
    q: 'What projects has Sherzod built?',
    a: 'Sherzod has built 11 real-world projects:\n\n1. E-Commerce Platform — React, TypeScript, Vite, Redux Toolkit\n2. Restaurant Website — Next.js, shadcn/ui, Tailwind CSS\n3. Edu CRM/ERP System — React, TypeScript, Ant Design\n4. Business Finance Manager — Full-stack, Node.js, PostgreSQL\n5. Toshkent Baliqchi — Fish restaurant landing page\n6. Nexora Labs — Corporate tech company site\n7. iPhone Store UZ — Apple product storefront\n8. Fitness Time Gym — Gym landing with pricing\n9. Parfume Market — Luxury perfume shop\n10. Barakah Restaurant — Full restaurant website\n11. Sherzoddev Portfolio — Next.js 15, Three.js, R3F\n\nSee them all on the Projects page!',
  },
  'Contact Info': {
    q: 'How can I contact Sherzod?',
    a: 'You can reach Sherzod via:\n\nEmail: sherzodusmonjonov734@gmail.com\nPhone: +998 94 205 5512\nTelegram: @WerzodUsmanov\nGitHub: github.com/m-werzod\n\nHe is currently available for freelance and full-time opportunities!',
  },
  'About Me': {
    q: 'Tell me about Sherzod.',
    a: 'Sherzodbek Usmonjonov is a Frontend Web Developer from Uzbekistan with 1+ year of experience building high-performance web apps. He specializes in React, Next.js, and creates motion designs and 3D web experiences using AI-powered tools. He speaks English fluently, understands Russian, and is available for freelance or full-time positions.',
  },
  'Education & AI': {
    q: "What is Sherzod's education and AI background?",
    a: "Sherzod graduated from Najot Ta'lim — one of Uzbekistan's leading tech schools — specializing in Frontend Web Development.\n\nBeyond coding, he has studied Prompt Engineering and is skilled at working with a wide range of AI tools to speed up development, create motion designs, and build 3D web experiences.\n\nHe is also planning to launch a social media presence to share his projects and development journey — stay tuned!",
  },
}

function smartReply(input: string): string {
  const q = input.toLowerCase()

  if (/contact|email|phone|telegram|reach|message|dm|call/.test(q))
    return knowledge['Contact Info'].a

  if (/project|built|work|app|site|website|ecommerce|restaurant|finance|crm|gym|parfume/.test(q))
    return knowledge['Projects'].a

  if (/tech|stack|technology|language|framework|react|next|typescript|tailwind|three|figma|node/.test(q))
    return knowledge['Tech Stack'].a

  if (/educat|school|study|najot|degree|certif|prompt|ai|artificial/.test(q))
    return knowledge['Education & AI'].a

  if (/who|about|sherzod|bio|background|experience|uzbek|developer/.test(q))
    return knowledge['About Me'].a

  if (/hire|available|freelance|job|opportunity|collaborate|price|cost|rate/.test(q))
    return "Sherzod is currently available for freelance projects and full-time opportunities.\n\nBest way to reach him:\n- Telegram: @WerzodUsmanov\n- Email: sherzodusmonjonov734@gmail.com\n\nHe typically responds within a few hours."

  if (/hello|hi |hey|sup|greet/.test(q))
    return "Hey there! I'm Sherzod's AI assistant. I can tell you about his projects, tech stack, experience, or how to get in touch. What would you like to know?"

  if (/salary|pay|rate|cost|budget/.test(q))
    return "For project pricing or salary expectations, it's best to discuss directly with Sherzod.\n\n- Telegram: @WerzodUsmanov\n- Email: sherzodusmonjonov734@gmail.com\n\nHe'll get back to you quickly!"

  return "I have info about Sherzod's projects, tech stack, experience, and contact details. Try the quick tabs above or ask something like:\n- \"What projects has he built?\"\n- \"How can I contact him?\"\n- \"What tech does he use?\""
}

interface Message { role: 'user' | 'assistant'; content: string }

const bubbleMessages = [
  'Ask me about Sherzod',
  'See his 11 projects',
  'Available for hire',
  'Ask about his tech stack',
]

export default function AIWidget() {
  const [open, setOpen]           = useState(false)
  const [bubble, setBubble]       = useState(true)
  const [bubbleIdx, setBubbleIdx] = useState(0)
  const [messages, setMessages]   = useState<Message[]>([
    { role: 'assistant', content: "Hi! I'm Sherzod's AI assistant. Ask me anything about his skills, projects, or how to get in touch!" },
  ])
  const [input, setInput]   = useState('')
  const [typing, setTyping] = useState(false)
  const messagesEndRef      = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, typing])

  useEffect(() => {
    if (!bubble || open) return
    const id = setInterval(() => setBubbleIdx((i) => (i + 1) % bubbleMessages.length), 4000)
    return () => clearInterval(id)
  }, [bubble, open])

  useEffect(() => {
    const id = setTimeout(() => setBubble(false), 18000)
    return () => clearTimeout(id)
  }, [])

  const openChat = () => { setOpen(true); setBubble(false) }

  const handleTab = (tab: Tab) => {
    const { q, a } = knowledge[tab]
    setMessages((prev) => [...prev, { role: 'user', content: q }])
    setTyping(true)
    setTimeout(() => {
      setTyping(false)
      setMessages((prev) => [...prev, { role: 'assistant', content: a }])
    }, 900)
  }

  const handleSend = () => {
    if (!input.trim()) return
    const userMsg = input.trim()
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }])
    setInput('')
    setTyping(true)
    setTimeout(() => {
      setTyping(false)
      setMessages((prev) => [...prev, { role: 'assistant', content: smartReply(userMsg) }])
    }, 1000)
  }

  return (
    <>
      {/* ── Speech bubble ──────────────────────────────────────────────── */}
      <AnimatePresence>
        {bubble && !open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.7, y: 12 }}
            animate={{ opacity: 1, scale: 1,   y: 0  }}
            exit={{   opacity: 0, scale: 0.7, y: 12 }}
            transition={{ type: 'spring', stiffness: 320, damping: 22 }}
            className="fixed bottom-[88px] right-6 z-50 max-w-[200px] cursor-pointer"
            onClick={openChat}
          >
            <div className="relative bg-white text-[#0a0f1e] text-xs font-semibold px-4 py-2.5 rounded-2xl shadow-xl shadow-black/30 leading-snug flex items-center gap-2">
              {/* Small colored icon per message */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="https://img.icons8.com/fluency/48/chatbot.png"
                alt=""
                width={16}
                height={16}
                className="w-4 h-4 object-contain shrink-0"
              />
              <AnimatePresence mode="wait">
                <motion.span
                  key={bubbleIdx}
                  initial={{ opacity: 0, y: 4  }}
                  animate={{ opacity: 1, y: 0  }}
                  exit={{   opacity: 0, y: -4 }}
                  transition={{ duration: 0.25 }}
                  className="block"
                >
                  {bubbleMessages[bubbleIdx]}
                </motion.span>
              </AnimatePresence>

              {/* Dismiss */}
              <button
                onClick={(e) => { e.stopPropagation(); setBubble(false) }}
                className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-slate-400 hover:bg-slate-500 text-white flex items-center justify-center text-[9px] leading-none transition-colors"
              >
                &#x2715;
              </button>

              {/* Tail */}
              <span className="absolute -bottom-2 right-5 w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-t-[8px] border-t-white" />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Toggle button ───────────────────────────────────────────────── */}
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
            // eslint-disable-next-line @next/next/no-img-element
            <img src="https://img.icons8.com/fluency/96/chatbot.png" alt="AI" className="w-9 h-9 object-contain" />
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

      {/* ── Chat panel ──────────────────────────────────────────────────── */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.94 }}
            animate={{ opacity: 1, y: 0,  scale: 1    }}
            exit={{   opacity: 0, y: 24, scale: 0.94 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className="fixed bottom-24 right-6 z-50 w-80 md:w-96 rounded-2xl border border-white/10 bg-[#0a1628]/95 backdrop-blur-xl shadow-2xl shadow-sky-950/50 overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-white/10 bg-gradient-to-r from-sky-950/50 to-transparent">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="https://img.icons8.com/fluency/96/chatbot.png" alt="AI" className="w-8 h-8" />
              <div className="flex-1">
                <p className="text-sm font-bold text-white">AI Assistant</p>
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <p className="text-xs text-slate-400">Online — Ask about Sherzod</p>
                </div>
              </div>
              <button
                onClick={() => setMessages([{ role: 'assistant', content: "Hi! I'm Sherzod's AI assistant. Ask me anything about his skills, projects, or how to get in touch!" }])}
                className="text-[10px] text-slate-600 hover:text-slate-400 transition-colors px-2 py-1 rounded-lg hover:bg-white/5"
              >
                Clear
              </button>
            </div>

            {/* Tabs */}
            <div className="flex gap-1.5 p-3 overflow-x-auto border-b border-white/5 bg-black/10">
              {(Object.keys(knowledge) as Tab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => handleTab(tab)}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white/5 hover:bg-[#38bdf8]/15 hover:text-[#38bdf8] text-slate-400 border border-white/5 hover:border-[#38bdf8]/30 transition-all whitespace-nowrap shrink-0"
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Messages */}
            <div className="h-64 overflow-y-auto p-4 flex flex-col gap-3">
              {messages.map((msg, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {msg.role === 'assistant' && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src="https://img.icons8.com/fluency/96/chatbot.png" alt="" className="w-5 h-5 self-end mb-0.5 mr-1.5 shrink-0" />
                  )}
                  <div className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed whitespace-pre-line ${
                    msg.role === 'user'
                      ? 'bg-[#38bdf8] text-[#020617] font-medium rounded-tr-sm'
                      : 'bg-white/5 text-slate-300 border border-white/5 rounded-tl-sm'
                  }`}>
                    {msg.content}
                  </div>
                </motion.div>
              ))}

              {typing && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start items-end gap-1.5">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src="https://img.icons8.com/fluency/96/chatbot.png" alt="" className="w-5 h-5 shrink-0" />
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
                placeholder="Ask anything about Sherzod..."
                className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-[#38bdf8]/40 transition-colors"
              />
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className="w-8 h-8 rounded-xl bg-[#38bdf8] flex items-center justify-center hover:bg-sky-300 transition-colors shrink-0 disabled:opacity-40"
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

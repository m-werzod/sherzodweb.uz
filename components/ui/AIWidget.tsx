'use client'
import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

type Tab = 'Tech Stack' | 'Projects' | 'Contact Info' | 'About Me' | 'Education & AI'

const knowledge: Record<Tab, { q: string; a: string }> = {
  'Tech Stack': {
    q: 'What technologies does Sherzod use?',
    a: 'Sherzod specializes in React, Next.js 15, TypeScript, and Tailwind CSS. He creates motion designs with Framer Motion, and builds 3D web experiences using Three.js / React Three Fiber with AI assistance. His toolbox also includes Git, Figma, Node.js, and Vercel for deployment.',
  },
  Projects: {
    q: 'What projects has Sherzod built?',
    a: 'Sherzod has built 10 real-world projects:\n\n1. E-Commerce Platform — React, TypeScript, Vite, Redux Toolkit, React Query\n2. Restaurant Website — Next.js, shadcn/ui, Tailwind CSS\n3. Edu CRM/ERP System — React, TypeScript, Ant Design, Axios\n4. Toshkent Baliqchi — Fish restaurant landing page\n5. Nexora Labs — Corporate tech company site\n6. iPhone Store UZ — Apple product storefront\n7. Fitness Time Gym — Gym landing with pricing & schedule\n8. Parfume Market — Luxury perfume shop\n9. Barakah Restaurant — Full restaurant website\n10. Sherzoddev Portfolio — This site (Next.js 15, Three.js, R3F)\n\nSee them all on the Projects page!',
  },
  'Contact Info': {
    q: 'How can I contact Sherzod?',
    a: 'You can reach Sherzod via:\n- Email: sherzodusmonjonov734@gmail.com\n- Phone: +998 94 205 5512\n- Telegram: @WerzodUsmanov\n- GitHub: github.com/m-werzod\nHe is currently available for freelance and full-time opportunities!',
  },
  'About Me': {
    q: 'Tell me about Sherzod.',
    a: 'Sherzodbek Usmonjonov is a Frontend Web Developer from Uzbekistan with 1+ year of experience building high-performance web apps. He specializes in React, Next.js, and also creates motion designs & 3D web experiences using AI-powered tools. He speaks English fluently, understands Russian, and is available for freelance or full-time positions.',
  },
  'Education & AI': {
    q: 'What is Sherzod\'s education and AI background?',
    a: 'Sherzod graduated from Najot Ta\'lim — one of Uzbekistan\'s leading tech schools — specializing in Frontend Web Development.\n\nBeyond coding, he has studied Prompt Engineering and is skilled at working with a wide range of AI tools to speed up development, create motion designs, and build 3D web experiences.\n\nHe is also planning to launch a social media presence to share his projects, development journey, and insights — so stay tuned! 🚀',
  },
}

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export default function AIWidget() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content:
        "Hi! I'm Sherzod's AI assistant. Ask me anything about his skills, projects, or how to get in touch!",
    },
  ])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, typing])

  const handleTab = (tab: Tab) => {
    const { q, a } = knowledge[tab]
    setMessages((prev) => [...prev, { role: 'user', content: q }])
    setTyping(true)
    setTimeout(() => {
      setTyping(false)
      setMessages((prev) => [...prev, { role: 'assistant', content: a }])
    }, 1200)
  }

  const handleSend = () => {
    if (!input.trim()) return
    setMessages((prev) => [...prev, { role: 'user', content: input }])
    setInput('')
    setTyping(true)
    setTimeout(() => {
      setTyping(false)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content:
            'Great question! For detailed information, feel free to browse the portfolio or contact Sherzod directly at sherzodusmonjonov734@gmail.com',
        },
      ])
    }, 1500)
  }

  return (
    <>
      {/* Toggle Button — fixed bottom-right */}
      <motion.button
        onClick={() => setOpen(!open)}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.95 }}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-2xl bg-gradient-to-br from-sky-500 to-blue-700 shadow-lg shadow-sky-900/50 flex items-center justify-center overflow-hidden"
        aria-label="AI Assistant"
      >
        <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.3 }}>
          {open ? (
            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          ) : (
            <img
              src="https://img.icons8.com/3d-fluency/94/chatbot.png"
              alt="AI"
              className="w-9 h-9 object-contain"
            />
          )}
        </motion.div>
        {/* Pulse ring */}
        {!open && (
          <motion.span
            className="absolute inset-0 rounded-2xl border-2 border-sky-400"
            animate={{ scale: [1, 1.4], opacity: [0.7, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        )}
      </motion.button>

      {/* Chat Panel */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            className="fixed bottom-24 right-6 z-50 w-80 md:w-96 rounded-2xl border border-white/10 bg-[#0a1628]/95 backdrop-blur-xl shadow-2xl shadow-sky-950/50 overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-white/10 bg-gradient-to-r from-sky-950/50 to-transparent">
              <img
                src="https://img.icons8.com/3d-fluency/94/chatbot.png"
                alt="AI"
                className="w-8 h-8"
              />
              <div>
                <p className="text-sm font-bold text-white">AI Assistant</p>
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <p className="text-xs text-slate-400">Online — Ask about Sherzod</p>
                </div>
              </div>
            </div>

            {/* Knowledge Base Tabs */}
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
            <div className="h-64 overflow-y-auto p-4 flex flex-col gap-3 scroll-smooth">
              {messages.map((msg, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed whitespace-pre-line ${
                      msg.role === 'user'
                        ? 'bg-[#38bdf8] text-[#020617] font-medium rounded-tr-sm'
                        : 'bg-white/5 text-slate-300 border border-white/5 rounded-tl-sm'
                    }`}
                  >
                    {msg.content}
                  </div>
                </motion.div>
              ))}
              {typing && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex justify-start"
                >
                  <div className="bg-white/5 border border-white/5 rounded-2xl rounded-tl-sm px-4 py-3 flex gap-1">
                    {[0, 0.15, 0.3].map((d, i) => (
                      <motion.span
                        key={i}
                        className="w-1.5 h-1.5 rounded-full bg-slate-400"
                        animate={{ y: [0, -4, 0] }}
                        transition={{ duration: 0.6, repeat: Infinity, delay: d }}
                      />
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
                placeholder="Ask anything..."
                className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-[#38bdf8]/40 transition-colors"
              />
              <button
                onClick={handleSend}
                className="w-8 h-8 rounded-xl bg-[#38bdf8] flex items-center justify-center hover:bg-sky-300 transition-colors shrink-0"
              >
                <img
                  src="https://cdn-icons-png.flaticon.com/512/3682/3682321.png"
                  alt="Send"
                  className="w-4 h-4 object-contain brightness-0"
                />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

'use client'
import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useLanguage } from '@/lib/i18n/LanguageContext'
import type { UIDict } from '@/lib/i18n/types'

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

type TabKey = 'techStack' | 'specializations' | 'projects' | 'contactInfo' | 'aboutMe'

function getKnowledge(ui: UIDict): Record<TabKey, { q: string; a: string }> {
  return {
    techStack: { q: ui.aiWidget.qTechStack, a: ui.aiWidget.aTechStack },
    specializations: { q: ui.aiWidget.qSpecializations, a: ui.aiWidget.aSpecializations },
    projects: { q: ui.aiWidget.qProjects, a: ui.aiWidget.aProjects },
    contactInfo: { q: ui.aiWidget.qContactInfo, a: ui.aiWidget.aContactInfo },
    aboutMe: { q: ui.aiWidget.qAboutMe, a: ui.aiWidget.aAboutMe },
  }
}

function smartReply(input: string, ui: UIDict): string {
  const q = input.toLowerCase()
  const knowledge = getKnowledge(ui)
  if (/contact|email|phone|telegram|reach|message|dm|whatsapp|call|instagram|linkedin|контакт|почта|телефон|телеграм|написать|связат|kontakt|telefon|bog'lan|yozing/.test(q))
    return knowledge.contactInfo.a
  if (/project|built|work|portfolio|app|site|website|ecommerce|restaurant|finance|crm|erp|gym|parfume|baliqchi|nexora|iphone|era ai|labour|migration|проект|работ|портфолио|создал|создан|loyiha|portfolio|yaratilgan/.test(q))
    return knowledge.projects.a
  if (/full[\s-]?stack|frontend|front-end|ai specialist|qa|q\.a\.|quality assurance|tester|specializ|фулстек|фронтенд|фронт-энд|тестировщик|специализац|fullstack|mutaxassis/.test(q))
    return knowledge.specializations.a
  if (/tech|stack|technology|language|framework|react|next|typescript|tailwind|three\.?js|figma|node|git|tools|\.net|dotnet|python|playwright|jest|vitest|postman|технологи|стек|фреймворк|texnologiya|dasturlash/.test(q))
    return knowledge.techStack.a
  if (/educat|school|study|najot|degree|certif|prompt|ai|artificial|who|about|sherzod|himself|bio|background|experience|uzbek|developer|years|образован|учил|диплом|сертифик|кто|о себе|биограф|опыт|разработчик|ta'lim|diplom|sertifikat|kim|tajriba|dasturchi/.test(q))
    return knowledge.aboutMe.a
  if (/hire|available|freelance|job|opportunity|work together|collaborate|price|cost|rate|нанять|доступен|фриланс|сотруднич|yollash|frilanser|hamkorlik/.test(q))
    return ui.aiWidget.replyHire
  if (/hello|hi |hey|sup|what's up|yo |greet|привет|здравству|salom|assalomu/.test(q))
    return ui.aiWidget.replyGreeting
  if (/salary|pay|rate|cost|price|budget|зарплата|оплата|цена|стоимост|бюджет|maosh|to'lov|narx|byudjet/.test(q))
    return ui.aiWidget.replySalary
  return ui.aiWidget.replyDefault
}

interface Message { role: 'user' | 'assistant'; content: string }

export default function AIWidget() {
  const { locale, ui } = useLanguage()
  const knowledge = getKnowledge(ui)
  const tabs: { key: TabKey; label: string }[] = [
    { key: 'techStack', label: ui.aiWidget.tabTechStack },
    { key: 'specializations', label: ui.aiWidget.tabSpecializations },
    { key: 'projects', label: ui.aiWidget.tabProjects },
    { key: 'contactInfo', label: ui.aiWidget.tabContactInfo },
    { key: 'aboutMe', label: ui.aiWidget.tabAboutMe },
  ]
  const bubbleMessages = [ui.aiWidget.bubble1, ui.aiWidget.bubble2, ui.aiWidget.bubble3, ui.aiWidget.bubble4]

  const [open, setOpen]           = useState(false)
  const [bubble, setBubble]       = useState(true)
  const [bubbleIdx, setBubbleIdx] = useState(0)
  const [messages, setMessages]   = useState<Message[]>([
    { role: 'assistant', content: ui.aiWidget.greeting },
  ])
  const [input, setInput]         = useState('')
  const [thinking, setThinking]   = useState(false)
  const [streaming, setStreaming] = useState(false)

  const messagesEndRef   = useRef<HTMLDivElement>(null)
  const streamTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Reset the conversation whenever the language changes, so it never mixes languages
  useEffect(() => {
    if (streamTimeoutRef.current) clearTimeout(streamTimeoutRef.current)
    setThinking(false)
    setStreaming(false)
    setMessages([{ role: 'assistant', content: ui.aiWidget.greeting }])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale])

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking])

  // Rotate bubble message every 4 s
  useEffect(() => {
    if (!bubble || open) return
    const id = setInterval(() => setBubbleIdx((i) => (i + 1) % bubbleMessages.length), 4000)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  const handleTab = (tab: TabKey) => {
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
    streamReply(smartReply(userMsg, ui))
  }

  const statusText = thinking || streaming ? ui.aiWidget.statusTyping : ui.aiWidget.statusOnline

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
                <p className="text-sm font-bold text-white">{ui.aiWidget.assistantTitle}</p>
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
                  setMessages([{ role: 'assistant', content: ui.aiWidget.greeting }])
                }}
                className="text-[10px] text-slate-600 hover:text-slate-400 transition-colors px-2 py-1 rounded-lg hover:bg-white/5"
                title={ui.aiWidget.clear}
              >
                {ui.aiWidget.clear}
              </button>
            </div>

            {/* Quick-topic tabs */}
            <div className="flex gap-1.5 p-3 overflow-x-auto border-b border-white/5 bg-black/10 scrollbar-none">
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => handleTab(tab.key)}
                  disabled={thinking || streaming}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white/5 hover:bg-[#38bdf8]/15 hover:text-[#38bdf8] text-slate-400 border border-white/5 hover:border-[#38bdf8]/30 transition-all whitespace-nowrap shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {tab.label}
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
                placeholder={ui.aiWidget.placeholder}
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

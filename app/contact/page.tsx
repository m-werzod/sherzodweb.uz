'use client'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Link from 'next/link'

const ICON = {
  gmail:    'https://cdn-icons-png.flaticon.com/512/281/281769.png',
  phone:    'https://img.icons8.com/3d-fluency/94/phone.png',
  telegram: 'https://cdn-icons-png.flaticon.com/512/2111/2111646.png',
  github:   'https://img.icons8.com/3d-fluency/94/github.png',
  instagram:'https://cdn-icons-png.flaticon.com/512/15713/15713420.png',
  linkedin: 'https://cdn-icons-png.flaticon.com/512/3992/3992606.png',
  sms:      'https://cdn-icons-png.flaticon.com/512/724/724664.png',
}

const contacts = [
  { label: 'Gmail',    value: 'sherzodusmonjonov734@gmail.com', href: 'mailto:sherzodusmonjonov734@gmail.com', icon: ICON.gmail    },
  { label: 'Phone',    value: '+998 94 205 5512',               href: 'tel:+998942055512',                    icon: ICON.phone    },
  { label: 'Telegram', value: '@WerzodUsmanov',                 href: 'https://t.me/WerzodUsmanov',           icon: ICON.telegram },
]

const socials = [
  { href: 'https://github.com/m-werzod',                               src: ICON.github,    alt: 'GitHub'    },
  { href: 'https://t.me/WerzodUsmanov',                                src: ICON.telegram,  alt: 'Telegram'  },
  { href: 'https://instagram.com/Sherzod_usmanovv',                    src: ICON.instagram, alt: 'Instagram' },
  { href: 'https://www.linkedin.com/in/sherzod-usmonjonov-8b22713b0/', src: ICON.linkedin,  alt: 'LinkedIn'  },
]

type Method = 'telegram' | 'email' | 'sms'

const methods = [
  { id: 'telegram' as Method, label: 'Telegram', desc: 'Fastest — usually replies within an hour',   icon: ICON.telegram, ring: 'border-sky-500/40 hover:border-sky-400/70 from-sky-600/10 to-sky-900/10'     },
  { id: 'email'    as Method, label: 'Gmail',    desc: 'Sends directly to inbox — replies in 24 h',  icon: ICON.gmail,    ring: 'border-red-500/40 hover:border-red-400/70 from-red-600/10 to-red-900/10'       },
  { id: 'sms'      as Method, label: 'SMS',      desc: 'Opens your messaging app pre-filled',         icon: ICON.phone,    ring: 'border-emerald-500/40 hover:border-emerald-400/70 from-emerald-600/10 to-emerald-900/10' },
]

type Status = { ok: boolean; via?: string; msg: string } | null

export default function ContactPage() {
  const [form, setForm]           = useState({ name: '', email: '', subject: '', message: '' })
  const [showModal, setShowModal] = useState(false)
  const [loading, setLoading]     = useState(false)
  const [status, setStatus]       = useState<Status>(null)

  const openModal = (e: React.FormEvent) => { e.preventDefault(); setStatus(null); setShowModal(true) }

  const send = async (method: Method) => {
    setShowModal(false)
    setLoading(true)

    try {
      /* ── SMS: open native app pre-filled ── */
      if (method === 'sms') {
        const body = encodeURIComponent(
          `Hi Sherzodbek!\nFrom: ${form.name} <${form.email}>\nSubject: ${form.subject}\n\n${form.message}`
        )
        window.open(`sms:+998942055512?body=${body}`, '_blank')
        setStatus({ ok: true, via: 'SMS', msg: 'SMS app opened — your message is pre-filled. Tap Send!' })
        setLoading(false)
        return
      }

      /* ── Telegram & Email: server-side auto-send ── */
      const res  = await fetch('/api/send', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ method, ...form }),
      })
      const data = await res.json()

      if (!res.ok || data.error) {
        /* Telegram fallback → open t.me with text */
        if (method === 'telegram') {
          const text = encodeURIComponent(
            `Hi! I'm ${form.name} (${form.email})\nSubject: ${form.subject}\n\n${form.message}`
          )
          window.open(`https://t.me/WerzodUsmanov?text=${text}`, '_blank')
          setStatus({ ok: true, via: 'Telegram', msg: 'Telegram opened — tap Send to deliver your message!' })
        } else {
          setStatus({ ok: false, msg: data.error || 'Something went wrong. Please try again.' })
        }
      } else {
        const via = method === 'telegram' ? 'Telegram' : 'Gmail'
        setStatus({ ok: true, via, msg: `Your message was sent via ${via}! I'll get back to you soon.` })
        setForm({ name: '', email: '', subject: '', message: '' })
      }
    } catch {
      setStatus({ ok: false, msg: 'Network error — please check your connection and try again.' })
    }

    setLoading(false)
  }

  return (
    <div className="min-h-screen pt-28 pb-24 px-6">
      <div className="max-w-5xl mx-auto">

        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/5 text-emerald-400 text-xs font-medium mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Currently Available for Work
          </div>
          <h1 className="text-4xl md:text-5xl font-black text-white mb-4">
            Let&apos;s <span className="text-[#38bdf8]">Connect</span>
          </h1>
          <p className="text-slate-400 max-w-xl mx-auto">
            Whether you have a project in mind, want to collaborate, or just want to say hi — my inbox is always open.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">

          {/* Left — contact cards */}
          <motion.div
            initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}
            className="lg:col-span-2 space-y-4"
          >
            {contacts.map((c) => (
              <Link key={c.label} href={c.href} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-4 p-4 rounded-2xl border border-white/10 bg-[#0a1628] hover:border-[#38bdf8]/30 transition-all group"
              >
                <img src={c.icon} alt={c.label} className="w-9 h-9 object-contain shrink-0" />
                <div>
                  <p className="text-[11px] text-slate-500 font-semibold uppercase tracking-widest mb-0.5">{c.label}</p>
                  <p className="text-sm text-slate-300 group-hover:text-[#38bdf8] transition-colors font-medium break-all">{c.value}</p>
                </div>
              </Link>
            ))}

            <div className="p-5 rounded-2xl border border-white/10 bg-[#0a1628]">
              <p className="text-[11px] text-slate-500 font-semibold uppercase tracking-widest mb-4">Follow Me</p>
              <div className="flex gap-3">
                {socials.map((s) => (
                  <Link key={s.alt} href={s.href} target="_blank" rel="noopener noreferrer"
                    className="w-10 h-10 flex items-center justify-center rounded-xl bg-white/5 border border-white/10 hover:border-[#38bdf8]/30 hover:bg-[#38bdf8]/5 transition-all group"
                  >
                    <img src={s.src} alt={s.alt} className="w-6 h-6 object-contain group-hover:scale-110 transition-transform" />
                  </Link>
                ))}
              </div>
            </div>

            <div className="p-5 rounded-2xl border border-white/10 bg-gradient-to-br from-sky-950/30 to-[#0a1628]">
              <p className="text-sm font-semibold text-white mb-1">Quick Response Guaranteed</p>
              <p className="text-xs text-slate-400">I typically respond within 24 hours. For urgent matters, reach out via Telegram.</p>
            </div>
          </motion.div>

          {/* Right — form */}
          <motion.div
            initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 }}
            className="lg:col-span-3"
          >
            {/* Status banner */}
            <AnimatePresence>
              {status && (
                <motion.div
                  initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
                  className={`mb-5 px-5 py-4 rounded-2xl border flex items-start gap-3 ${
                    status.ok
                      ? 'bg-emerald-950/30 border-emerald-500/30 text-emerald-300'
                      : 'bg-red-950/30 border-red-500/30 text-red-300'
                  }`}
                >
                  <span className="text-xl shrink-0 mt-0.5">{status.ok ? '✅' : '❌'}</span>
                  <div className="flex-1">
                    {status.ok && status.via && (
                      <p className="font-bold text-sm mb-0.5">Message sent via {status.via}!</p>
                    )}
                    <p className="text-sm opacity-90">{status.msg}</p>
                  </div>
                  <button onClick={() => setStatus(null)} className="text-xs opacity-50 hover:opacity-100 shrink-0">✕</button>
                </motion.div>
              )}
            </AnimatePresence>

            <form onSubmit={openModal} className="p-8 rounded-2xl border border-white/10 bg-[#0a1628] space-y-5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-2">Name</label>
                  <input type="text" required value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="Your name"
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-[#38bdf8]/50 focus:bg-[#38bdf8]/5 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-2">Email</label>
                  <input type="email" required value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    placeholder="your@email.com"
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-[#38bdf8]/50 focus:bg-[#38bdf8]/5 transition-all"
                  />
                </div>
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-2">Subject</label>
                <input type="text" required value={form.subject}
                  onChange={(e) => setForm({ ...form, subject: e.target.value })}
                  placeholder="What's this about?"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-[#38bdf8]/50 focus:bg-[#38bdf8]/5 transition-all"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-2">Message</label>
                <textarea required value={form.message}
                  onChange={(e) => setForm({ ...form, message: e.target.value })}
                  placeholder="Tell me about your project..."
                  rows={5}
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-[#38bdf8]/50 focus:bg-[#38bdf8]/5 transition-all resize-none"
                />
              </div>
              <motion.button
                type="submit" disabled={loading}
                whileHover={{ scale: loading ? 1 : 1.02 }}
                whileTap={{ scale: loading ? 1 : 0.98 }}
                className="w-full py-4 bg-[#38bdf8] text-[#020617] font-bold rounded-xl hover:bg-sky-300 transition-all hover:shadow-lg hover:shadow-sky-400/25 flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                    </svg>
                    Sending…
                  </>
                ) : (
                  <>
                    Send Message
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="22" y1="2" x2="11" y2="13"/>
                      <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                    </svg>
                  </>
                )}
              </motion.button>
            </form>
          </motion.div>
        </div>
      </div>

      {/* ── Method Modal ────────────────────────────────────────────── */}
      <AnimatePresence>
        {showModal && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center px-4 bg-[#020617]/85 backdrop-blur-md"
            onClick={() => setShowModal(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.88, y: 28 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.88, y: 28 }}
              transition={{ type: 'spring', damping: 20, stiffness: 280 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-sm bg-[#060f22] border border-white/10 rounded-3xl overflow-hidden shadow-2xl shadow-black/70"
            >
              <div className="h-1 w-full bg-gradient-to-r from-[#38bdf8] via-sky-400 to-indigo-500" />

              <div className="p-8">
                <div className="flex flex-col items-center text-center mb-7">
                  <div className="w-14 h-14 rounded-2xl bg-[#38bdf8]/10 border border-[#38bdf8]/20 flex items-center justify-center mb-4">
                    <svg className="w-7 h-7 text-[#38bdf8]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="22" y1="2" x2="11" y2="13"/>
                      <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                    </svg>
                  </div>
                  <h2 className="text-xl font-black text-white mb-1">How to send it?</h2>
                  <p className="text-xs text-slate-400">Pick your preferred channel — message sends instantly</p>
                </div>

                <div className="space-y-3">
                  {methods.map((m, i) => (
                    <motion.button
                      key={m.id}
                      initial={{ opacity: 0, x: -16 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.07 }}
                      whileHover={{ scale: 1.02, x: 4 }}
                      whileTap={{ scale: 0.97 }}
                      onClick={() => send(m.id)}
                      className={`w-full flex items-center gap-4 px-5 py-4 rounded-2xl bg-gradient-to-r border transition-all duration-200 text-left ${m.ring}`}
                    >
                      <img src={m.icon} alt={m.label} className="w-10 h-10 object-contain shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-bold text-white">{m.label}</p>
                        <p className="text-xs text-slate-400 mt-0.5">{m.desc}</p>
                      </div>
                      <svg className="w-4 h-4 text-slate-500 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="9 18 15 12 9 6"/>
                      </svg>
                    </motion.button>
                  ))}
                </div>

                <button
                  onClick={() => setShowModal(false)}
                  className="w-full mt-5 py-2.5 text-xs text-slate-600 hover:text-slate-400 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

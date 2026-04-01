'use client'
import { useState } from 'react'
import { motion } from 'framer-motion'
import Link from 'next/link'

const contacts = [
  {
    label: 'Email',
    value: 'sherzodusmonjonov734@gmail.com',
    href: 'mailto:sherzodusmonjonov734@gmail.com',
    icon: 'https://cdn-icons-png.flaticon.com/512/732/732200.png',
  },
  {
    label: 'Phone',
    value: '+998 94 205 5512',
    href: 'tel:+998942055512',
    icon: 'https://cdn-icons-png.flaticon.com/512/455/455705.png',
  },
  {
    label: 'Telegram',
    value: '@WerzodUsmanov',
    href: 'https://t.me/WerzodUsmanov',
    icon: 'https://cdn-icons-png.flaticon.com/512/2111/2111646.png',
  },
]

const socials = [
  { href: 'https://github.com/m-werzod', src: 'https://img.icons8.com/3d-fluency/94/github.png', alt: 'GitHub' },
  {
    href: 'https://t.me/WerzodUsmanov',
    src: 'https://cdn-icons-png.flaticon.com/512/2111/2111646.png',
    alt: 'Telegram',
  },
  {
    href: 'https://instagram.com/Sherzod_usmanovv',
    src: 'https://cdn-icons-png.flaticon.com/512/15713/15713420.png',
    alt: 'Instagram',
  },
  { href: '#', src: 'https://cdn-icons-png.flaticon.com/512/3992/3992606.png', alt: 'LinkedIn' },
]

export default function ContactPage() {
  const [form, setForm] = useState({ name: '', email: '', subject: '', message: '' })
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
  }

  return (
    <div className="min-h-screen pt-28 pb-24 px-6">
      <div className="max-w-5xl mx-auto">

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-16"
        >
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

          {/* Contact Info */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="lg:col-span-2 space-y-4"
          >
            {contacts.map((c) => (
              <Link
                key={c.label}
                href={c.href}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-start gap-4 p-5 rounded-2xl border border-white/10 bg-[#0a1628] hover:border-[#38bdf8]/30 transition-all group"
              >
                <img src={c.icon} alt={c.label} className="w-6 h-6 object-contain shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-1">{c.label}</p>
                  <p className="text-sm text-slate-300 group-hover:text-[#38bdf8] transition-colors font-medium break-all">
                    {c.value}
                  </p>
                </div>
              </Link>
            ))}

            {/* Socials */}
            <div className="p-5 rounded-2xl border border-white/10 bg-[#0a1628]">
              <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-4">Follow Me</p>
              <div className="flex gap-3">
                {socials.map((s) => (
                  <Link
                    key={s.alt}
                    href={s.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-10 h-10 flex items-center justify-center rounded-xl bg-white/5 border border-white/10 hover:border-[#38bdf8]/30 hover:bg-[#38bdf8]/5 transition-all group"
                  >
                    <img
                      src={s.src}
                      alt={s.alt}
                      className="w-5 h-5 object-contain group-hover:scale-110 transition-transform"
                    />
                  </Link>
                ))}
              </div>
            </div>

            {/* Response time */}
            <div className="p-5 rounded-2xl border border-white/10 bg-gradient-to-br from-sky-950/30 to-[#0a1628]">
              <p className="text-sm font-semibold text-white mb-1">Quick Response Guaranteed</p>
              <p className="text-xs text-slate-400">
                I typically respond within 24 hours. For urgent matters, reach out via Telegram.
              </p>
            </div>
          </motion.div>

          {/* Contact Form */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 }}
            className="lg:col-span-3"
          >
            {submitted ? (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="h-full flex flex-col items-center justify-center gap-6 p-12 rounded-2xl border border-emerald-500/30 bg-emerald-950/20 text-center"
              >
                <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center text-3xl">
                  ✓
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white mb-2">Message Sent!</h3>
                  <p className="text-slate-400 text-sm">
                    Thank you for reaching out. I&apos;ll get back to you within 24 hours.
                  </p>
                </div>
                <button
                  onClick={() => setSubmitted(false)}
                  className="px-6 py-2.5 text-sm font-semibold border border-white/15 rounded-xl hover:bg-white/5 transition-colors text-slate-400"
                >
                  Send Another
                </button>
              </motion.div>
            ) : (
              <form onSubmit={handleSubmit} className="p-8 rounded-2xl border border-white/10 bg-[#0a1628] space-y-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                      Name
                    </label>
                    <input
                      type="text"
                      required
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      placeholder="Your name"
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-[#38bdf8]/50 focus:bg-[#38bdf8]/5 transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                      Email
                    </label>
                    <input
                      type="email"
                      required
                      value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                      placeholder="your@email.com"
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-[#38bdf8]/50 focus:bg-[#38bdf8]/5 transition-all"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    Subject
                  </label>
                  <input
                    type="text"
                    required
                    value={form.subject}
                    onChange={(e) => setForm({ ...form, subject: e.target.value })}
                    placeholder="What's this about?"
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-[#38bdf8]/50 focus:bg-[#38bdf8]/5 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    Message
                  </label>
                  <textarea
                    required
                    value={form.message}
                    onChange={(e) => setForm({ ...form, message: e.target.value })}
                    placeholder="Tell me about your project..."
                    rows={5}
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-[#38bdf8]/50 focus:bg-[#38bdf8]/5 transition-all resize-none"
                  />
                </div>
                <motion.button
                  type="submit"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="w-full py-4 bg-[#38bdf8] text-[#020617] font-bold rounded-xl hover:bg-sky-300 transition-all hover:shadow-lg hover:shadow-sky-400/25 flex items-center justify-center gap-2"
                >
                  Send Message
                  <img src="https://cdn-icons-png.flaticon.com/512/3682/3682321.png" alt="Send" className="w-4 h-4 object-contain" />
                </motion.button>
              </form>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  )
}

'use client'
import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'

const links = [
  {
    href: '/',
    label: 'Home',
    icon: <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>,
  },
  {
    href: '/about',
    label: 'About',
    icon: <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>,
  },
  {
    href: '/projects',
    label: 'Projects',
    icon: <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>,
  },
  {
    href: '/contact',
    label: 'Contact',
    icon: <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>,
  },
]

export default function Navbar() {
  const [scrolled, setScrolled]   = useState(false)
  const [menuOpen, setMenuOpen]   = useState(false)
  const pathname                  = usePathname()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => { setMenuOpen(false) }, [pathname])

  useEffect(() => {
    document.body.style.overflow = menuOpen ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [menuOpen])

  return (
    <>
      <motion.header
        initial={{ y: -80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          scrolled
            ? 'bg-[#020617]/80 backdrop-blur-xl border-b border-white/5 shadow-lg'
            : 'bg-transparent'
        }`}
      >
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          {/* Logo */}
          <Link href="/" className="relative group">
            <span className="text-2xl font-black tracking-tight">
              <span className="text-white">S</span>
              <span className="text-[#38bdf8]">U</span>
            </span>
            <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-[#38bdf8] group-hover:w-full transition-all duration-300" />
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center gap-1">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-medium tracking-wide transition-all duration-200 group ${
                  pathname === link.href
                    ? 'text-[#38bdf8] bg-[#38bdf8]/8'
                    : 'text-slate-400 hover:text-white hover:bg-white/5'
                }`}
              >
                <span className={`shrink-0 transition-transform duration-200 group-hover:scale-110 ${pathname !== link.href ? 'opacity-70 group-hover:opacity-100' : ''}`}>
                  {link.icon}
                </span>
                {link.label}
              </Link>
            ))}
            <Link
              href="/contact"
              className="ml-3 px-4 py-2 text-sm font-bold bg-gradient-to-r from-[#38bdf8] to-sky-400 text-[#020617] rounded-xl hover:from-sky-300 hover:to-[#38bdf8] transition-all duration-200 hover:shadow-lg hover:shadow-sky-400/30"
            >
              Hire Me
            </Link>
          </nav>

          {/* Hamburger */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden relative z-[60] flex flex-col gap-1.5 p-2"
            aria-label="Toggle menu"
          >
            <motion.span animate={{ rotate: menuOpen ? 45 : 0, y: menuOpen ? 8 : 0 }} transition={{ duration: 0.25 }} className="w-6 h-0.5 bg-white block" />
            <motion.span animate={{ opacity: menuOpen ? 0 : 1, scaleX: menuOpen ? 0 : 1 }} transition={{ duration: 0.2 }} className="w-6 h-0.5 bg-white block" />
            <motion.span animate={{ rotate: menuOpen ? -45 : 0, y: menuOpen ? -8 : 0 }} transition={{ duration: 0.25 }} className="w-6 h-0.5 bg-white block" />
          </button>
        </div>
      </motion.header>

      {/* ── Right-side mobile drawer ── */}
      <AnimatePresence>
        {menuOpen && (
          <>
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
              onClick={() => setMenuOpen(false)}
              className="fixed inset-0 z-[55] bg-[#020617]/70 backdrop-blur-sm md:hidden"
            />

            <motion.div
              key="drawer"
              initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 28, stiffness: 260 }}
              className="fixed top-0 right-0 bottom-0 z-[58] w-72 bg-[#040e1f] border-l border-white/8 shadow-2xl md:hidden flex flex-col"
            >
              <div className="h-1 w-full bg-gradient-to-r from-[#38bdf8] to-indigo-500" />

              <div className="flex items-center justify-between px-6 h-16 border-b border-white/5">
                <span className="text-xl font-black">
                  <span className="text-white">S</span>
                  <span className="text-[#38bdf8]">U</span>
                </span>
                <button
                  onClick={() => setMenuOpen(false)}
                  className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center hover:bg-white/10 transition-colors"
                >
                  <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Mobile nav links with SVG icons */}
              <nav className="flex flex-col px-4 pt-6 gap-1 flex-1">
                {links.map((link, i) => (
                  <motion.div
                    key={link.href}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.05 + i * 0.06 }}
                  >
                    <Link
                      href={link.href}
                      className={`flex items-center gap-3.5 px-4 py-3.5 rounded-xl text-sm font-semibold transition-all duration-200 ${
                        pathname === link.href
                          ? 'bg-[#38bdf8]/10 text-[#38bdf8] border border-[#38bdf8]/20'
                          : 'text-slate-400 hover:text-white hover:bg-white/5'
                      }`}
                    >
                      <span className={pathname === link.href ? 'text-[#38bdf8]' : 'text-slate-500'}>
                        {link.icon}
                      </span>
                      {link.label}
                      {pathname === link.href && (
                        <span className="ml-auto w-1.5 h-1.5 rounded-full bg-[#38bdf8]" />
                      )}
                    </Link>
                  </motion.div>
                ))}
              </nav>

              <div className="px-4 pb-8 pt-4 border-t border-white/5">
                <Link
                  href="/contact"
                  className="block w-full py-3 text-sm font-bold bg-[#38bdf8] text-[#020617] rounded-xl text-center hover:bg-sky-300 transition-colors"
                >
                  Hire Me
                </Link>
                <p className="text-center text-xs text-slate-600 mt-4">Available for Work</p>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}

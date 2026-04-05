'use client'
import { useEffect, useState } from 'react'
import { usePathname } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'

export default function PageLoader() {
  const pathname = usePathname()
  const [loading, setLoading] = useState(false)
  const [prev, setPrev] = useState(pathname)

  /* Stop loader when route finishes */
  useEffect(() => {
    if (pathname !== prev) {
      setLoading(false)
      setPrev(pathname)
    }
  }, [pathname, prev])

  /* Start loader on any same-origin internal link click */
  useEffect(() => {
    const handle = (e: MouseEvent) => {
      const a = (e.target as HTMLElement).closest('a')
      if (!a?.href) return
      try {
        const url = new URL(a.href)
        const isSame = url.hostname === window.location.hostname
        const isDiff = url.pathname !== window.location.pathname
        const isInternal = !a.target && !a.href.startsWith('mailto') && !a.href.startsWith('tel')
        if (isSame && isDiff && isInternal) setLoading(true)
      } catch {}
    }
    document.addEventListener('click', handle, true)
    return () => document.removeEventListener('click', handle, true)
  }, [])

  return (
    <AnimatePresence>
      {loading && (
        <>
          {/* Thin neon top bar */}
          <motion.div
            key="bar"
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 0.85 }}
            exit={{ scaleX: 1, opacity: 0 }}
            transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
            style={{ transformOrigin: 'left center', boxShadow: '0 0 12px 2px #38bdf8' }}
            className="fixed top-0 left-0 right-0 h-[3px] z-[200] bg-[#38bdf8]"
          />
          {/* Full-page dim overlay with centered spinner */}
          <motion.div
            key="overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-[199] bg-[#020617]/60 backdrop-blur-[2px] flex items-center justify-center"
          >
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
              className="w-8 h-8 rounded-full border-2 border-[#38bdf8]/20 border-t-[#38bdf8]"
            />
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

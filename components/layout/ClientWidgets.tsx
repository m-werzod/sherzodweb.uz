'use client'
import dynamic from 'next/dynamic'

// These are client-only widgets that must not block SSR/first paint
const AIWidget   = dynamic(() => import('@/components/ui/AIWidget'),   { ssr: false })
const PageLoader = dynamic(() => import('@/components/ui/PageLoader'), { ssr: false })

export default function ClientWidgets() {
  return (
    <>
      <PageLoader />
      <AIWidget />
    </>
  )
}

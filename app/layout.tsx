import type { Metadata } from 'next'
import './globals.css'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import AIWidget from '@/components/ui/AIWidget'
import PageLoader from '@/components/ui/PageLoader'

export const metadata: Metadata = {
  title: 'Sherzodbek Usmonjonov — Frontend Web Developer',
  description: 'Frontend Web Developer crafting high-performance digital experiences with React, Next.js & motion design.',
  keywords: ['Frontend Developer', 'React', 'Next.js', 'Uzbekistan'],
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#020617] text-white antialiased">
        <PageLoader />
        <Navbar />
        <main>{children}</main>
        <Footer />
        <AIWidget />
      </body>
    </html>
  )
}

import type { Metadata } from 'next'
import './globals.css'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import AIWidget from '@/components/ui/AIWidget'

export const metadata: Metadata = {
  title: 'Sherzodbek Usmonjonov — Frontend Architect',
  description: 'Frontend Architect Crafting High-Performance Digital Experiences.',
  keywords: ['Frontend Developer', 'React', 'Next.js', 'Uzbekistan'],
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#020617] text-white antialiased">
        <Navbar />
        <main>{children}</main>
        <Footer />
        <AIWidget />
      </body>
    </html>
  )
}

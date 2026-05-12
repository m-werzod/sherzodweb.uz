import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  preload: true,
  variable: '--font-inter',
})

export const metadata: Metadata = {
  title: 'Sherzodbek Usmonjonov — Frontend Web Developer',
  description:
    'Frontend Web Developer crafting high-performance digital experiences with React, Next.js & motion design.',
  keywords: ['Frontend Developer', 'React', 'Next.js', 'TypeScript', 'Uzbekistan', 'Sherzodbek Usmonjonov'],
  authors: [{ name: 'Sherzodbek Usmonjonov', url: 'https://sherzoddev.com' }],
  openGraph: {
    title: 'Sherzodbek Usmonjonov — Frontend Web Developer',
    description: 'Building high-performance web experiences with React & Next.js.',
    url: 'https://sherzoddev.com',
    siteName: 'Sherzoddev',
    locale: 'en_US',
    type: 'website',
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#020617',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${inter.variable}`}>
      <head>
        <link rel="preconnect" href="https://cdn-icons-png.flaticon.com" />
        <link rel="preconnect" href="https://img.icons8.com" />
        <link rel="preconnect" href="https://cdn.jsdelivr.net" crossOrigin="anonymous" />
        <link rel="dns-prefetch" href="https://cdn-icons-png.flaticon.com" />
        <link rel="dns-prefetch" href="https://img.icons8.com" />
        <link rel="dns-prefetch" href="https://cdn.jsdelivr.net" />
      </head>
      <body className={`${inter.className} bg-[#020617] text-white antialiased`}>
        {children}
      </body>
    </html>
  )
}

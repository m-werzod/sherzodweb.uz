import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import ClientWidgets from '@/components/layout/ClientWidgets'
import { LanguageProvider } from '@/lib/i18n/LanguageContext'

export default function PortfolioLayout({ children }: { children: React.ReactNode }) {
  return (
    <LanguageProvider>
      <ClientWidgets />
      <Navbar />
      <main>{children}</main>
      <Footer />
    </LanguageProvider>
  )
}

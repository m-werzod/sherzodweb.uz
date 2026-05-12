import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import ClientWidgets from '@/components/layout/ClientWidgets'

export default function PortfolioLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <ClientWidgets />
      <Navbar />
      <main>{children}</main>
      <Footer />
    </>
  )
}

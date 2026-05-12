import type { Metadata } from 'next'
import { DashboardProvider } from './_lib/store'
import Sidebar from './_components/Sidebar'
import { ToastProvider } from './_components/Toast'
import KeyboardShortcuts from './_components/KeyboardShortcuts'
import TopBar from './_components/TopBar'

export const metadata: Metadata = {
  title: 'FinTrack — Business Dashboard',
  description: 'Track income, expenses, and financial performance for your business.',
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <DashboardProvider>
      <ToastProvider>
        <div className="min-h-screen bg-[#090912] flex">
          <Sidebar />

          {/* Main content area */}
          <div className="flex-1 ml-60 min-h-screen flex flex-col overflow-x-hidden">
            {/* Subtle dot-grid background */}
            <div
              className="pointer-events-none fixed inset-0 ml-60 opacity-[0.025]"
              style={{
                backgroundImage: 'radial-gradient(circle, #6366f1 1px, transparent 1px)',
                backgroundSize: '28px 28px',
              }}
            />
            <TopBar />
            <main className="flex-1 relative z-10">
              {children}
            </main>
          </div>

          <KeyboardShortcuts />
        </div>
      </ToastProvider>
    </DashboardProvider>
  )
}

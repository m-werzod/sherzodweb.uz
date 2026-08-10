import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'SMM Coach',
  description: 'AI-powered Instagram growth coach',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // The actual <html> + <body> + locale provider live in app/[locale]/layout.tsx.
  // Next requires a root layout, so this passes children straight through.
  return children;
}

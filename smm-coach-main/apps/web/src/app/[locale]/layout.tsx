import type { Metadata } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import { Bricolage_Grotesque, JetBrains_Mono } from 'next/font/google';
import { NextIntlClientProvider } from 'next-intl';
import { getMessages, setRequestLocale } from 'next-intl/server';
import { notFound } from 'next/navigation';
import { Toaster } from 'sonner';
import { locales, type Locale } from '@/i18n/config';
import { Providers } from '@/components/providers';
import { themeInitScript } from '@/lib/theme';

// Self-host the two custom fonts via Next.js so the page doesn't depend on
// Google's CDN at runtime (which intermittently fails in dev). Bricolage
// powers display/heading text; JetBrains Mono powers eyebrows + numbers.
const bricolage = Bricolage_Grotesque({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-bricolage',
  display: 'swap',
});
const jetbrains = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-jetbrains',
  display: 'swap',
});

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export const metadata: Metadata = {
  // Static template "%s | SMM Coach" — child layouts/pages can override
  // the leading segment; bare "SMM Coach" if nothing is set.
  title: { default: 'SMM Coach', template: '%s · SMM Coach' },
  description:
    "Instagram'da o'sish uchun AI agentlar siz bilan birga ishlaydi — SMM Coach.",
};

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!locales.includes(locale as Locale)) notFound();
  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <html
      lang={locale}
      className={`${GeistSans.variable} ${GeistMono.variable} ${bricolage.variable} ${jetbrains.variable}`}
      suppressHydrationWarning
    >
      <body>
        {/* Apply the saved accent palette before first paint so the theme
            persists on every page (not just while Settings is mounted) and
            there's no violet→theme flash. */}
        <script dangerouslySetInnerHTML={{ __html: themeInitScript() }} />
        <NextIntlClientProvider messages={messages}>
          <Providers>
            {children}
            <Toaster richColors closeButton theme="dark" />
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}

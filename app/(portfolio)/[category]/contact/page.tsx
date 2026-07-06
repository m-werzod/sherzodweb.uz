import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import ContactPageContent from '@/components/sections/ContactPageContent'
import { categories, categorySlugs, isCategoryKey } from '@/lib/resumeData'

export function generateStaticParams() {
  return categorySlugs.map((category) => ({ category }))
}
export const dynamicParams = false

export async function generateMetadata({ params }: { params: Promise<{ category: string }> }): Promise<Metadata> {
  const { category } = await params
  if (!isCategoryKey(category)) return {}
  const data = categories[category]
  return { title: `Contact — ${data.fullTitle} | Sherzodbek Usmonjonov` }
}

export default async function CategoryContactPage({ params }: { params: Promise<{ category: string }> }) {
  const { category } = await params
  if (!isCategoryKey(category)) notFound()
  return <ContactPageContent category={category} />
}

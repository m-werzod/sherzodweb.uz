import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import CategoryAbout from '@/components/category/CategoryAbout'
import { categories, categorySlugs, isCategoryKey } from '@/lib/resumeData'

export function generateStaticParams() {
  return categorySlugs.map((category) => ({ category }))
}
export const dynamicParams = false

export async function generateMetadata({ params }: { params: Promise<{ category: string }> }): Promise<Metadata> {
  const { category } = await params
  if (!isCategoryKey(category)) return {}
  const data = categories[category]
  return {
    title: `About — ${data.fullTitle} | Sherzodbek Usmonjonov`,
    description: data.summary[0],
  }
}

export default async function CategoryAboutPage({ params }: { params: Promise<{ category: string }> }) {
  const { category } = await params
  if (!isCategoryKey(category)) notFound()
  return <CategoryAbout data={categories[category]} />
}

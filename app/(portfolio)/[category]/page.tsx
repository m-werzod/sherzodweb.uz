import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import CategoryHero from '@/components/category/CategoryHero'
import ProjectsPreview from '@/components/sections/ProjectsPreview'
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
    title: `${data.fullTitle} — Sherzodbek Usmonjonov`,
    description: data.summary[0],
  }
}

export default async function CategoryPage({ params }: { params: Promise<{ category: string }> }) {
  const { category } = await params
  if (!isCategoryKey(category)) notFound()

  return (
    <>
      <CategoryHero category={category} />
      <ProjectsPreview />
    </>
  )
}

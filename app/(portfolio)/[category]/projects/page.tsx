import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import ProjectsPageContent from '@/components/sections/ProjectsPageContent'
import { categories, categorySlugs, isCategoryKey } from '@/lib/resumeData'

export function generateStaticParams() {
  return categorySlugs.map((category) => ({ category }))
}
export const dynamicParams = false

export async function generateMetadata({ params }: { params: Promise<{ category: string }> }): Promise<Metadata> {
  const { category } = await params
  if (!isCategoryKey(category)) return {}
  const data = categories[category]
  return { title: `Projects — ${data.fullTitle} | Sherzodbek Usmonjonov` }
}

export default async function CategoryProjectsPage({ params }: { params: Promise<{ category: string }> }) {
  const { category } = await params
  if (!isCategoryKey(category)) notFound()

  return <ProjectsPageContent category={category} />
}

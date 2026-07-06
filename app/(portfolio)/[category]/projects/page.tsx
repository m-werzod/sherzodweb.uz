import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import ProjectsPageContent from '@/components/sections/ProjectsPageContent'
import { categories, categorySlugs, isCategoryKey } from '@/lib/resumeData'
import { featuredProjects, moreProjects } from '@/lib/projects'

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
  const data = categories[category]

  return (
    <ProjectsPageContent
      eyebrow={`${data.label} Portfolio`}
      titlePrefix=""
      titleHighlight={`${data.label} Projects`}
      subtitle={`Production platforms built as a ${data.fullTitle.toLowerCase()} — from the Era AI aggregation platform and Labour Migration Agency system to e-commerce, CRM, and fintech apps.`}
      featured={featuredProjects}
      more={moreProjects}
      contactHref={`/${data.slug}/contact`}
    />
  )
}

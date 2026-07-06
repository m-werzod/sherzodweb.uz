import ProjectsPageContent from '@/components/sections/ProjectsPageContent'
import { featuredProjects, moreProjects } from '@/lib/projects'

export default function ProjectsPage() {
  return <ProjectsPageContent featured={featuredProjects} more={moreProjects} />
}

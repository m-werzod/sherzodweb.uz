import type { Locale } from './config'
import type { Project } from '@/components/ui/ProjectCard'
import * as projectsEn from '@/lib/projects'
import * as projectsRu from './projects.ru'
import * as projectsUz from './projects.uz'

export interface ProjectsBundle {
  flagshipProjects: Project[]
  homeHighlightPick: Project
  homeHighlights: Project[]
  featuredProjects: Project[]
  moreProjects: Project[]
  allProjects: Project[]
}

export function getProjects(locale: Locale): ProjectsBundle {
  switch (locale) {
    case 'ru':
      return projectsRu
    case 'uz':
      return projectsUz
    default:
      return projectsEn
  }
}

import type { Locale } from './config'
import { categories as categoriesEn, categorySlugs, type CategoryData, type CategoryKey } from '@/lib/resumeData'
import { categories as categoriesRu } from './resumeData.ru'
import { categories as categoriesUz } from './resumeData.uz'

export function getCategories(locale: Locale): Record<CategoryKey, CategoryData> {
  switch (locale) {
    case 'ru':
      return categoriesRu
    case 'uz':
      return categoriesUz
    default:
      return categoriesEn
  }
}

export function getCategoryList(locale: Locale): CategoryData[] {
  const categories = getCategories(locale)
  return categorySlugs.map((slug) => categories[slug])
}

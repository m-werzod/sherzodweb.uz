'use client'
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { defaultLocale, isLocale, type Locale } from './config'
import { getUI } from './getUI'
import { getCategories, getCategoryList } from './getCategories'
import { getProjects, type ProjectsBundle } from './getProjects'
import type { UIDict } from './types'
import type { CategoryData, CategoryKey } from '@/lib/resumeData'

const STORAGE_KEY = 'sherzoddev-locale'

interface LanguageContextValue {
  locale: Locale
  setLocale: (locale: Locale) => void
  ui: UIDict
  categories: Record<CategoryKey, CategoryData>
  categoryList: CategoryData[]
  projects: ProjectsBundle
}

const LanguageContext = createContext<LanguageContextValue | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(defaultLocale)

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved && isLocale(saved)) setLocaleState(saved)
  }, [])

  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  const setLocale = (next: Locale) => {
    setLocaleState(next)
    window.localStorage.setItem(STORAGE_KEY, next)
  }

  const value = useMemo<LanguageContextValue>(
    () => ({
      locale,
      setLocale,
      ui: getUI(locale),
      categories: getCategories(locale),
      categoryList: getCategoryList(locale),
      projects: getProjects(locale),
    }),
    [locale]
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used within a LanguageProvider')
  return ctx
}

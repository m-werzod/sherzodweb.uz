export type Locale = 'en' | 'ru' | 'uz'

export const locales: Locale[] = ['en', 'ru', 'uz']
export const defaultLocale: Locale = 'en'

export interface LocaleMeta {
  code: Locale
  label: string
  nativeLabel: string
  flag: string
}

export const localeMeta: Record<Locale, LocaleMeta> = {
  en: { code: 'en', label: 'English', nativeLabel: 'English', flag: 'https://flagcdn.com/w40/us.png' },
  ru: { code: 'ru', label: 'Russian', nativeLabel: 'Русский', flag: 'https://flagcdn.com/w40/ru.png' },
  uz: { code: 'uz', label: 'Uzbek', nativeLabel: "O'zbek", flag: 'https://flagcdn.com/w40/uz.png' },
}

export const localeList: LocaleMeta[] = locales.map((l) => localeMeta[l])

export function isLocale(value: string): value is Locale {
  return value === 'en' || value === 'ru' || value === 'uz'
}

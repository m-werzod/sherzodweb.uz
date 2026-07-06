import type { Locale } from './config'
import type { UIDict } from './types'
import { ui as uiEn } from './ui.en'
import { ui as uiRu } from './ui.ru'
import { ui as uiUz } from './ui.uz'

export function getUI(locale: Locale): UIDict {
  switch (locale) {
    case 'ru':
      return uiRu
    case 'uz':
      return uiUz
    default:
      return uiEn
  }
}

/** Splits text on `**...**` markers and returns plain segments, used to render an emphasized mid-sentence phrase. */
export function splitHighlight(text: string): { text: string; emphasis: boolean }[] {
  const parts = text.split('**')
  return parts.map((part, i) => ({ text: part, emphasis: i % 2 === 1 }))
}

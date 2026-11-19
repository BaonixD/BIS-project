import { useSyncExternalStore } from 'react'
import { en, kk } from './messages'

export const LOCALES = ['ru', 'kk', 'en'] as const
export type Locale = (typeof LOCALES)[number]
export const LOCALE_STORAGE_KEY = 'bis.locale'
const listeners = new Set<() => void>()

function savedLocale(): Locale {
  try {
    const saved = window.localStorage.getItem(LOCALE_STORAGE_KEY)
    return LOCALES.includes(saved as Locale) ? (saved as Locale) : 'ru'
  } catch {
    return 'ru'
  }
}

let locale: Locale = savedLocale()

export function getLocale(): Locale {
  return locale
}
export function getIntlLocale(): string {
  return { ru: 'ru-RU', kk: 'kk-KZ', en: 'en-GB' }[locale]
}

function updateDocument() {
  if (typeof document !== 'undefined') {
    document.documentElement.lang = locale
    document.title = 'TezJet'
  }
}
updateDocument()

export function setLocale(next: Locale): void {
  if (!LOCALES.includes(next)) return
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, next)
  } catch {
    /* Storage may be disabled. */
  }
  if (locale === next) {
    updateDocument()
    return
  }
  locale = next
  updateDocument()
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
export function useLocale(): Locale {
  return useSyncExternalStore(subscribe, getLocale, () => 'ru')
}

export function translate(
  language: Locale,
  message: string,
  values: Readonly<Record<string, unknown>> = {},
): string {
  const key = message.trim().replace(/\s+/g, ' ')
  const dictionary = language === 'en' ? en : language === 'kk' ? kk : undefined
  const translated = dictionary?.[key] ?? key
  const text = translated.replace(/\{(\w+)\}/g, (placeholder, name: string) =>
    name in values ? String(values[name] ?? '') : placeholder,
  )
  return `${/^\s/.test(message) ? ' ' : ''}${text}${/\s$/.test(message) ? ' ' : ''}`
}

export function t(message: string, values?: Readonly<Record<string, unknown>>): string {
  return translate(locale, message, values)
}

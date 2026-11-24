import { useSyncExternalStore } from 'react'

export type ThemeChoice = 'system' | 'light' | 'dark'
export const THEME_CHOICES: readonly ThemeChoice[] = ['system', 'light', 'dark']
/** Also read by the inline script in index.html, so the first paint has the right theme. */
export const THEME_STORAGE_KEY = 'tezjet.theme'
const listeners = new Set<() => void>()
const media =
  typeof window !== 'undefined' && window.matchMedia
    ? window.matchMedia('(prefers-color-scheme: dark)')
    : null

function saved(): ThemeChoice {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY)
    return THEME_CHOICES.includes(value as ThemeChoice) ? (value as ThemeChoice) : 'system'
  } catch {
    return 'system'
  }
}

let choice: ThemeChoice = typeof window === 'undefined' ? 'system' : saved()

function resolvedDark(): boolean {
  return choice === 'dark' || (choice === 'system' && Boolean(media?.matches))
}

function apply(): void {
  if (typeof document === 'undefined') return
  document.documentElement.dataset.theme = resolvedDark() ? 'dark' : 'light'
  listeners.forEach((listener) => listener())
}

media?.addEventListener('change', apply)
apply()

export function setTheme(next: ThemeChoice): void {
  choice = next
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, next)
  } catch {
    /* Storage may be disabled. */
  }
  apply()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useThemeChoice(): ThemeChoice {
  return useSyncExternalStore(subscribe, () => choice, () => 'system')
}

/** True while the app is dark (chosen, or the system's choice). */
export function useDarkTheme(): boolean {
  return useSyncExternalStore(subscribe, resolvedDark, () => false)
}

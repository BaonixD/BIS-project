import { useEffect, useState, useSyncExternalStore } from 'react'
import { useDarkTheme } from './theme'

export type MapThemeChoice = 'auto' | 'day' | 'night'
export const MAP_THEME_STORAGE_KEY = 'tezjet.map-theme'
const CHOICES: readonly MapThemeChoice[] = ['auto', 'day', 'night']
const listeners = new Set<() => void>()

function saved(): MapThemeChoice {
  try {
    const value = window.localStorage.getItem(MAP_THEME_STORAGE_KEY)
    return CHOICES.includes(value as MapThemeChoice) ? (value as MapThemeChoice) : 'auto'
  } catch {
    return 'auto'
  }
}

let choice: MapThemeChoice = typeof window === 'undefined' ? 'auto' : saved()

export function setMapTheme(next: MapThemeChoice): void {
  choice = next
  try {
    window.localStorage.setItem(MAP_THEME_STORAGE_KEY, next)
  } catch {
    /* Storage may be disabled. */
  }
  listeners.forEach((listener) => listener())
}

export function useMapThemeChoice(): MapThemeChoice {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => choice,
    () => 'auto',
  )
}

/** The hour in Almaty, whatever the device's time zone. */
export function almatyHour(date = new Date()): number {
  const hour = new Intl.DateTimeFormat('en-GB', {
    hour: 'numeric',
    hourCycle: 'h23',
    timeZone: 'Asia/Almaty',
  }).format(date)
  return Number(hour)
}

export function isAlmatyNight(date = new Date()): boolean {
  const hour = almatyHour(date)
  return hour >= 20 || hour < 6
}

/** «Түнгі Алматы»: chosen night, or auto at night in Almaty (20:00–6:00) or in the dark theme. */
export function useNightMap(): boolean {
  const current = useMapThemeChoice()
  const dark = useDarkTheme()
  const [night, setNight] = useState(isAlmatyNight)
  useEffect(() => {
    const timer = window.setInterval(() => setNight(isAlmatyNight()), 60_000)
    return () => window.clearInterval(timer)
  }, [])
  return current === 'night' || (current === 'auto' && (night || dark))
}

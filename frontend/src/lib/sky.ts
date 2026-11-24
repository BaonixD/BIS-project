import { useEffect, useState, useSyncExternalStore } from 'react'
import { almatyHour } from './map-theme'

export type SkyPhase = 'dawn' | 'day' | 'dusk' | 'night'
export type SkyChoice = 'auto' | SkyPhase
export const SKY_CHOICES: readonly SkyChoice[] = ['auto', 'dawn', 'day', 'dusk', 'night']
export const SKY_STORAGE_KEY = 'tezjet.sky'
const listeners = new Set<() => void>()

function saved(): SkyChoice {
  try {
    const value = window.localStorage.getItem(SKY_STORAGE_KEY)
    return SKY_CHOICES.includes(value as SkyChoice) ? (value as SkyChoice) : 'auto'
  } catch {
    return 'auto'
  }
}

let choice: SkyChoice = typeof window === 'undefined' ? 'auto' : saved()

export function setSkyChoice(next: SkyChoice): void {
  choice = next
  try {
    window.localStorage.setItem(SKY_STORAGE_KEY, next)
  } catch {
    /* Storage may be disabled. */
  }
  listeners.forEach((listener) => listener())
}

export function useSkyChoice(): SkyChoice {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => choice,
    () => 'auto',
  )
}

/** Dawn 5–8, day 8–17, dusk 17–20, night otherwise (Almaty hours). */
export function phaseAt(hour: number): SkyPhase {
  if (hour >= 5 && hour < 8) return 'dawn'
  if (hour >= 8 && hour < 17) return 'day'
  if (hour >= 17 && hour < 20) return 'dusk'
  return 'night'
}

/** The sky the user picked, or the current one in Almaty (re-checked every minute). */
export function useSkyPhase(): SkyPhase {
  const picked = useSkyChoice()
  const [current, setCurrent] = useState(() => phaseAt(almatyHour()))
  useEffect(() => {
    const timer = window.setInterval(() => setCurrent(phaseAt(almatyHour())), 60_000)
    return () => window.clearInterval(timer)
  }, [])
  return picked === 'auto' ? current : picked
}

import { useEffect, useState } from 'react'
import { almatyHour } from './map-theme'

export type SkyPhase = 'dawn' | 'day' | 'dusk' | 'night'

/** Dawn 5–8, day 8–17, dusk 17–20, night otherwise (Almaty hours). */
export function phaseAt(hour: number): SkyPhase {
  if (hour >= 5 && hour < 8) return 'dawn'
  if (hour >= 8 && hour < 17) return 'day'
  if (hour >= 17 && hour < 20) return 'dusk'
  return 'night'
}

/** The current sky phase in Almaty, re-checked every minute. */
export function useSkyPhase(): SkyPhase {
  const [phase, setPhase] = useState(() => phaseAt(almatyHour()))
  useEffect(() => {
    const timer = window.setInterval(() => setPhase(phaseAt(almatyHour())), 60_000)
    return () => window.clearInterval(timer)
  }, [])
  return phase
}

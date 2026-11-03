import { useEffect, useState } from 'react'
import type { Coordinates } from '@/api'
import { ALMATY_CENTER } from '@/lib/geo'

/** Browser position once; Almaty centre until it arrives or when it is denied. */
export function useMyLocation(): { point: Coordinates; located: boolean } {
  const [state, setState] = useState<{ point: Coordinates; located: boolean }>({ point: ALMATY_CENTER, located: false })

  useEffect(() => {
    if (!('geolocation' in navigator)) return
    let active = true
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        if (active) setState({ point: { latitude: coords.latitude, longitude: coords.longitude }, located: true })
      },
      () => undefined,
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 60_000 },
    )
    return () => {
      active = false
    }
  }, [])

  return state
}

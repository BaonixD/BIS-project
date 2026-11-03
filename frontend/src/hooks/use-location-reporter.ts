import { useEffect, useRef, useState } from 'react'
import type { Coordinates } from '@/api'
import { LOCATION_REPORT_MS } from './polling'
import { useSendLocation } from './use-driver'

const GEOLOCATION_SUPPORTED = typeof navigator !== 'undefined' && 'geolocation' in navigator

export type LocationSource = 'gps' | 'manual' | 'none'

export interface LocationReporter {
  /** GPS failed or is missing: the driver must pick a point on the map. */
  needsManualPoint: boolean
  source: LocationSource
  position: Coordinates | null
  lastSentAt: string | null
  sendError: Error | null
}

function useGpsPosition(enabled: boolean) {
  const [position, setPosition] = useState<Coordinates | null>(null)
  const [failed, setFailed] = useState(!GEOLOCATION_SUPPORTED)

  useEffect(() => {
    if (!enabled || !GEOLOCATION_SUPPORTED) return
    const watchId = navigator.geolocation.watchPosition(
      ({ coords }) => {
        setFailed(false)
        setPosition({ latitude: coords.latitude, longitude: coords.longitude })
      },
      () => setFailed(true),
      { enableHighAccuracy: true, maximumAge: 5_000, timeout: 15_000 },
    )
    return () => navigator.geolocation.clearWatch(watchId)
  }, [enabled])

  return { position: failed ? null : position, failed }
}

/** While `enabled` (driver online), sends the position every 10 s: GPS first, else `manualPoint`. */
export function useLocationReporter(
  enabled: boolean,
  manualPoint: Coordinates | null,
): LocationReporter {
  const gps = useGpsPosition(enabled)
  const { mutate, data, error } = useSendLocation()
  const position = gps.position ?? (gps.failed ? manualPoint : null)
  const positionRef = useRef(position)
  const hasPosition = position !== null

  useEffect(() => {
    positionRef.current = position
  }, [position])

  useEffect(() => {
    if (!enabled || !hasPosition) return
    const send = () => {
      if (positionRef.current) mutate(positionRef.current)
    }
    send()
    const timer = window.setInterval(send, LOCATION_REPORT_MS)
    return () => window.clearInterval(timer)
  }, [enabled, hasPosition, mutate])

  const manualActive = enabled && gps.failed && manualPoint !== null
  useEffect(() => {
    if (manualActive && positionRef.current) mutate(positionRef.current)
  }, [manualActive, manualPoint, mutate])

  return {
    needsManualPoint: gps.failed,
    source: gps.position ? 'gps' : position ? 'manual' : 'none',
    position,
    lastSentAt: data?.location_updated_at ?? null,
    sendError: error,
  }
}

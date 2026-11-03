import type { Coordinates } from '@/api'
import { formatDistance } from '@/lib/format'

const EARTH_RADIUS_M = 6_371_000
/** City driving to the pickup, ~18 km/h: 1,2 км → ~4 мин as in the mockup. */
const PICKUP_SPEED_M_PER_MIN = 300

export function haversineM(a: Coordinates, b: Coordinates): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180
  const dLat = toRad(b.latitude - a.latitude)
  const dLon = toRad(b.longitude - a.longitude)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.latitude)) * Math.cos(toRad(b.latitude)) * Math.sin(dLon / 2) ** 2
  return Math.round(2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h)))
}

/** «Подача 1,2 км · ~4 мин» from the driver's last point; «Подача рядом» without one. */
export function pickupLine(driver: Coordinates | null | undefined, pickup: Coordinates): string {
  if (!driver) return 'Подача рядом'
  const meters = haversineM(driver, pickup)
  const minutes = Math.max(1, Math.round(meters / PICKUP_SPEED_M_PER_MIN))
  return `Подача ${formatDistance(meters)} · ~${minutes} мин`
}

/** «02:15» since `fromIso`. */
export function formatWait(fromIso: string | null, now: number): string {
  const seconds = fromIso ? Math.max(0, Math.floor((now - Date.parse(fromIso)) / 1000)) : 0
  const mm = String(Math.floor(seconds / 60)).padStart(2, '0')
  const ss = String(seconds % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

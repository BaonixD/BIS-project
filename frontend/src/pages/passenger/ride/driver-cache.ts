import { useEffect } from 'react'
import type { DriverCard } from '@/api'

const KEY = 'bis.rideDriver'

/**
 * `GET /rides/{id}` returns the driver only while the ride is active; the receipt and the rating
 * card of a finished ride (Figma 5:499, 24:668) still name the driver, so the last card is kept
 * for the browser session.
 */
export function useRememberedDriver(rideId: string, driver: DriverCard | null | undefined): DriverCard | null {
  useEffect(() => {
    if (driver) sessionStorage.setItem(`${KEY}:${rideId}`, JSON.stringify(driver))
  }, [rideId, driver])
  if (driver) return driver
  try {
    return JSON.parse(sessionStorage.getItem(`${KEY}:${rideId}`) ?? 'null') as DriverCard | null
  } catch {
    return null
  }
}

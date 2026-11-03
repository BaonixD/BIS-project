import type { Coordinates, DriverCard as DriverCardData } from '@/api'
import { useReverseGeocode } from '@/hooks/use-geocoding'
import { shortName } from '@/pages/passenger/model/format'

/** Address title of a point (Nominatim, «Точка на карте» as a fallback). */
export function usePlaceTitle(point: Coordinates | null | undefined): string | undefined {
  return useReverseGeocode(point ?? null).data?.title
}

export function vehicleText(driver: DriverCardData): string {
  const vehicle = driver.vehicle
  return vehicle ? `${vehicle.make} ${vehicle.model} · ${vehicle.color}` : ''
}

/** «Арман Н. · 123 ABC 02». */
export function driverLine(driver: DriverCardData | null): string | null {
  if (!driver) return null
  const plate = driver.vehicle?.plate_number
  return plate ? `${shortName(driver.full_name)} · ${plate}` : shortName(driver.full_name)
}

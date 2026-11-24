import type { Coordinates, DriverCard as DriverCardData } from '@/api'
import { useReverseGeocode } from '@/hooks/use-geocoding'
import { shortName } from '@/pages/passenger/model/format'
import { t } from '@/i18n/core'

/** Address title of a point (Nominatim); «Точка на карте» once the lookup fails or finds nothing. */
export function usePlaceTitle(point: Coordinates | null | undefined): string | undefined {
  const query = useReverseGeocode(point ?? null)
  if (query.data?.title) return query.data.title
  if (query.isError || query.isSuccess) return t('Точка на карте')
  return undefined
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

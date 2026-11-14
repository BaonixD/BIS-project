import { t, getIntlLocale } from '@/i18n/core'
import { api, unwrap } from './client'
import { TARIFFS } from './passenger-types'
import type {
  MyRating as GeneratedMyRating,
  RatingSummary as GeneratedRatingSummary,
  Tariff,
} from './passenger-types'
import type { AdminDriver, Driver, Offer, RideDetails } from './types'
export { TARIFFS } from './passenger-types'
export type { Tariff }
export const TARIFF_LABELS = (): Record<Tariff, string> => ({
  economy: t('Эконом'),
  comfort: t('Комфорт'),
  comfort_plus: t('Комфорт+'),
  business: t('Бизнес'),
})
export type RatingSummary = GeneratedRatingSummary
export type MyRating = GeneratedMyRating
export type NextDriver = Driver
export type NextAdminDriver = AdminDriver
export type NextOffer = Offer
export type NextRide = RideDetails
export const PASSENGER_TAGS = ['on_time', 'polite', 'clean'] as const
export type PassengerTag = (typeof PASSENGER_TAGS)[number]
export const PASSENGER_TAG_LABELS = (): Record<PassengerTag, string> => ({
  on_time: t('Вовремя'),
  polite: t('Вежливый'),
  clean: t('Чисто'),
})
export interface PassengerRatingRequest {
  stars: number
  tags: PassengerTag[]
  comment: string | null
}
export const RATING_ALREADY_EXISTS = 'rating_already_exists'
export function postPassengerRating(rideId: string, body: PassengerRatingRequest) {
  return unwrap(
    api.POST('/api/v1/rides/{ride_id}/rating', { params: { path: { ride_id: rideId } }, body }),
  )
}
export function postApproveDriver(
  driverId: string,
  carClass: Tariff | null,
): Promise<NextAdminDriver> {
  return unwrap(
    api.POST('/api/v1/admin/drivers/{driver_id}/approve', {
      params: { path: { driver_id: driverId } },
      body: carClass ? { car_class: carClass } : undefined,
    }),
  )
}
export function patchDriverCarClass(driverId: string, carClass: Tariff): Promise<NextAdminDriver> {
  return unwrap(
    api.PATCH('/api/v1/admin/drivers/{driver_id}', {
      params: { path: { driver_id: driverId } },
      body: { car_class: carClass },
    }),
  )
}
/** «★ 4,8», or null while there is no rating yet. */
export function formatRating(rating: RatingSummary | null | undefined): string | null {
  if (!rating || rating.count === 0 || rating.average === null) return null
  return `★ ${new Intl.NumberFormat(getIntlLocale(), { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(rating.average)}`
}
export function vehicleCategories(
  vehicle:
    | {
        categories?: readonly Tariff[]
        car_class: Tariff
      }
    | null
    | undefined,
): readonly Tariff[] {
  if (!vehicle) return []
  return vehicle.categories ?? TARIFFS.slice(0, TARIFFS.indexOf(vehicle.car_class) + 1)
}
export function vehicleCategoryLabel(vehicle: {
  categories?: readonly Tariff[]
  car_class: Tariff
}): string {
  return vehicleCategories(vehicle)
    .map((category) => TARIFF_LABELS()[category])
    .join(', ')
}

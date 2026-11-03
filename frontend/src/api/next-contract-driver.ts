// TODO: удалить после регенерации openapi — типы и вызовы контракта main (d127a9e: тарифы, vehicle.car_class,
// Kaspi при назначении, оценки), которых ещё нет в schema.d.ts. Сверено со схемой main; регенерация в этой ветке
// ломает экраны пассажира (QuoteResponse, tariff в RideCreateRequest), поэтому её делает сборка.
import { api, unwrap } from './client'
import type { AdminDriver, Driver, Offer, PaymentMethod, RideDetails, VehicleInput } from './types'

export const TARIFFS = ['economy', 'comfort', 'comfort_plus', 'business'] as const
export type Tariff = (typeof TARIFFS)[number]

export const TARIFF_LABELS: Record<Tariff, string> = {
  economy: 'Эконом',
  comfort: 'Комфорт',
  comfort_plus: 'Комфорт+',
  business: 'Бизнес',
}

/** `RatingSummaryResponse`: `average` is null until the first rating. */
export interface RatingSummary {
  average: number | null
  count: number
}

type NextVehicle = VehicleInput & { car_class?: Tariff }

/** `GET /drivers/me`: the vehicle carries the admin-set `car_class`, plus the driver's rating. */
export type NextDriver = Omit<Driver, 'vehicle'> & { vehicle: NextVehicle | null; rating?: RatingSummary | null }

export type NextAdminDriver = Omit<AdminDriver, 'vehicle'> & { vehicle: NextVehicle | null }

/**
 * `OfferResponse` with the ride tariff and the passenger rating.
 * `payment_method` is NOT in the backend offer (Figma 6:125 shows «Оплата наличными»): the row stays
 * hidden until the backend adds it.
 */
export type NextOffer = Offer & {
  tariff?: Tariff
  passenger_rating?: RatingSummary | null
  payment_method?: PaymentMethod | null
}

/** `MyRating`: what the current user already gave for this ride. */
export interface MyRating {
  stars: number
  tags: string[]
  comment: string | null
}

export type NextRide = RideDetails & { tariff?: Tariff; my_rating?: MyRating | null }

export const PASSENGER_TAGS = ['on_time', 'polite', 'clean'] as const
export type PassengerTag = (typeof PASSENGER_TAGS)[number]

export const PASSENGER_TAG_LABELS: Record<PassengerTag, string> = {
  on_time: 'Вовремя',
  polite: 'Вежливый',
  clean: 'Чисто',
}

/** `POST /rides/{id}/rating` → 201 `RatingResponse` (after `completed`; repeat — `409 rating_already_exists`). */
export interface PassengerRatingRequest {
  stars: number
  tags: PassengerTag[]
  comment: string | null
}

export const RATING_ALREADY_EXISTS = 'rating_already_exists'

interface LooseInit {
  params: { path: Record<string, string> }
  body?: unknown
}

type LooseResult = Promise<{ data?: unknown; error?: unknown; response: Response }>

/** The typed client without path checking, for routes the generated schema does not know yet. */
const loose = api as unknown as {
  POST: (path: string, init: LooseInit) => LooseResult
  PATCH: (path: string, init: LooseInit) => LooseResult
}

export function postPassengerRating(rideId: string, body: PassengerRatingRequest): Promise<unknown> {
  return unwrap(loose.POST('/api/v1/rides/{ride_id}/rating', { params: { path: { ride_id: rideId } }, body }))
}

export function postApproveDriver(driverId: string, carClass: Tariff | null): Promise<NextAdminDriver> {
  return unwrap(
    loose.POST('/api/v1/admin/drivers/{driver_id}/approve', {
      params: { path: { driver_id: driverId } },
      body: carClass ? { car_class: carClass } : undefined,
    }),
  ) as Promise<NextAdminDriver>
}

export function patchDriverCarClass(driverId: string, carClass: Tariff): Promise<NextAdminDriver> {
  return unwrap(
    loose.PATCH('/api/v1/admin/drivers/{driver_id}', {
      params: { path: { driver_id: driverId } },
      body: { car_class: carClass },
    }),
  ) as Promise<NextAdminDriver>
}

/** «★ 4,8», or null while there is no rating yet. */
export function formatRating(rating: RatingSummary | null | undefined): string | null {
  if (!rating || rating.count === 0 || rating.average === null) return null
  return `★ ${rating.average.toFixed(1).replace('.', ',')}`
}

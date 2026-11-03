import type { Readable } from 'openapi-typescript-helpers'
import type { components } from './schema'

type Schema<K extends keyof components['schemas']> = Readable<components['schemas'][K]>

/** Passenger-side aliases of the tariff and rating schemas (generated from `openapi.json`). */
export type Tariff = Schema<'Tariff'>
export type QuoteOption = Schema<'TariffOption'>
export type RideCreateRequest = Schema<'RideCreateRequest'>
export type RatingTag = Schema<'RatingTag'>
export type RatingRequest = Schema<'RatingRequest'>
export type RatingResponse = Schema<'RatingResponse'>
export type MyRating = Schema<'MyRating'>
export type RatingSummary = Schema<'RatingSummaryResponse'>
export type VehicleCard = Schema<'VehicleCard'>

export const TARIFFS = ['economy', 'comfort', 'comfort_plus', 'business'] as const satisfies readonly Tariff[]

/** Tags a passenger gives a driver (`on_time` and `clean` are the driver's tags for passengers). */
export const PASSENGER_RATING_TAGS = ['polite', 'clean_car', 'smooth_driving', 'knows_route'] as const satisfies readonly RatingTag[]
export type PassengerRatingTag = (typeof PASSENGER_RATING_TAGS)[number]

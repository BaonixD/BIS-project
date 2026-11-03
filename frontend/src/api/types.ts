import type { Readable } from 'openapi-typescript-helpers'
import type { components } from './schema'

/** Schemas as openapi-fetch returns them (`Readable` turns tuples into arrays). */
type Schemas = { [K in keyof components['schemas']]: Readable<components['schemas'][K]> }

export type Coordinates = Schemas['Coordinates']
export type UserRole = Schemas['UserRole']
export type User = Schemas['UserResponse']
export type Session = Schemas['SessionResponse']
export type MyProfile = Schemas['MyProfileResponse']
export type MyProfileUpdate = Schemas['MyProfileUpdate']
export type RegisterRequest = Schemas['RegisterRequest']
export type LoginRequest = Schemas['LoginRequest']

export type RideStatus = Schemas['RideStatus']
export type RouteResult = Schemas['RouteResult']
export type Quote = Schemas['QuoteResponse']
export type Ride = Schemas['RideResponse']
export type RideDetails = Schemas['RideDetailsResponse']
export type RideSummary = Schemas['RideSummary']
export type DriverCard = Schemas['DriverCard']

export type Driver = Schemas['DriverResponse']
export type DriverProfileUpdate = Schemas['DriverProfileUpdate']
export type VehicleInput = Schemas['VehicleInput']
export type ApprovalStatus = Schemas['ApprovalStatus']
export type Offer = Schemas['OfferResponse']
export type OfferStatus = Schemas['OfferStatus']

export type Payment = Schemas['PaymentResponse']
export type PaymentMethod = Schemas['PaymentMethod']
export type PaymentStatus = Schemas['PaymentStatus']

export type AdminDriver = Schemas['AdminDriverResponse']
export type AdminUser = Schemas['AdminUserResponse']

export type ErrorEnvelope = Schemas['ErrorResponse']

export interface Page<T> {
  items: T[]
  limit: number
  offset: number
  total: number
}

export interface PageParams {
  limit?: number
  offset?: number
}

export const ACTIVE_RIDE_STATUSES = [
  'searching',
  'assigned',
  'arrived',
  'in_progress',
] as const satisfies readonly RideStatus[]

export const DRIVER_ACTIVE_RIDE_STATUSES = [
  'assigned',
  'arrived',
  'in_progress',
] as const satisfies readonly RideStatus[]

export function isRideActive(status: RideStatus): boolean {
  return (ACTIVE_RIDE_STATUSES as readonly RideStatus[]).includes(status)
}

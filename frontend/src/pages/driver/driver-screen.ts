import type { PaymentStatus } from '@/api'
import { formatMoney } from '@/lib/format'
import type { NextDriver, NextOffer, NextRide } from '@/api/driver-types'

export type DriverScreen =
  | { kind: 'pending' }
  | { kind: 'offline' }
  | { kind: 'online' }
  | { kind: 'offer'; offer: NextOffer }
  | { kind: 'ride'; ride: NextRide }
  | { kind: 'cancelled'; ride: NextRide }
  | { kind: 'collect-cash'; ride: NextRide }
  | { kind: 'completed'; ride: NextRide; paidBy: 'kaspi' | 'cash' }

export interface DriverScreenInput {
  driver: NextDriver
  /** The ride the driver is (or just was) on, until they dismiss its final screen. */
  ride: NextRide | null
  offer: NextOffer | null
  /** Fresher than `ride.payment_status` right after «Наличные получены». */
  paymentStatus?: PaymentStatus | null
}

function rideScreen(ride: NextRide, paymentStatus: PaymentStatus | null): DriverScreen | null {
  switch (ride.status) {
    case 'assigned':
    case 'arrived':
    case 'in_progress':
      return { kind: 'ride', ride }
    case 'cancelled':
    case 'no_driver':
      return { kind: 'cancelled', ride }
    case 'completed':
      if (ride.payment_method === 'cash' && paymentStatus !== 'paid') return { kind: 'collect-cash', ride }
      return { kind: 'completed', ride, paidBy: ride.payment_method === 'cash' ? 'cash' : 'kaspi' }
    case 'searching':
      return null
  }
}

/** Which driver screen to show: the ride first, then approval, the offer and availability. */
export function selectDriverScreen({ driver, ride, offer, paymentStatus }: DriverScreenInput): DriverScreen {
  const fromRide = ride ? rideScreen(ride, paymentStatus ?? ride.payment_status) : null
  if (fromRide) return fromRide
  if (driver.approval_status !== 'approved') return { kind: 'pending' }
  if (!driver.online) return { kind: 'offline' }
  if (offer && offer.status === 'pending') return { kind: 'offer', offer }
  return { kind: 'online' }
}

export const RIDE_STEPS = ['Назначен', 'На месте', 'В пути', 'Готово']

export function rideStep(status: NextRide['status']): number {
  if (status === 'assigned') return 0
  if (status === 'arrived') return 1
  if (status === 'in_progress') return 2
  return 3
}

/** «Наличные · 2 200 ₸ · получить после поездки» / «Kaspi · уже оплачено · 2 200 ₸». */
export function paymentSummary(ride: NextRide): string {
  const amount = formatMoney(ride.amount_kzt)
  if (ride.payment_method === 'kaspi_link') return `Kaspi · уже оплачено · ${amount}`
  return `Наличные · ${amount} · получить после поездки`
}

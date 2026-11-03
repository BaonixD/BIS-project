import type { PaymentMethod, PaymentStatus, RideStatus } from '@/api'

export type RideScreen =
  | 'searching'
  | 'driver_found'
  | 'on_the_way'
  | 'arrived'
  | 'in_progress'
  | 'pay_cash'
  | 'completed'
  | 'cancelled'
  | 'no_driver'

interface RideState {
  status: RideStatus
  payment_method: PaymentMethod | null
  payment_status: PaymentStatus | null
}

/**
 * Which passenger screen a ride shows (`GET /rides/{id}` is polled every 3 s).
 * Kaspi: «Водитель найден — оплата прошла» once, when the assigned ride is paid, then tracking.
 * Cash: after completion «Оплатите наличными» until the driver confirms the cash.
 */
export function rideScreen(ride: RideState, { driverFoundSeen }: { driverFoundSeen: boolean }): RideScreen {
  switch (ride.status) {
    case 'searching':
      return 'searching'
    case 'assigned':
      return isPaidKaspi(ride) && !driverFoundSeen ? 'driver_found' : 'on_the_way'
    case 'arrived':
      return 'arrived'
    case 'in_progress':
      return 'in_progress'
    case 'completed':
      return ride.payment_method === 'cash' && ride.payment_status !== 'paid' ? 'pay_cash' : 'completed'
    case 'cancelled':
      return 'cancelled'
    case 'no_driver':
      return 'no_driver'
  }
}

export function isPaidKaspi(ride: Pick<RideState, 'payment_method' | 'payment_status'>): boolean {
  return ride.payment_method === 'kaspi_link' && ride.payment_status === 'paid'
}

/** A driver released the ride: it is searching again after having a driver. */
export function wasReleased(previous: RideStatus | undefined, next: RideStatus): boolean {
  return next === 'searching' && (previous === 'assigned' || previous === 'arrived')
}

/** Keep polling a completed cash ride until the driver confirms the payment. */
export function needsPolling(ride: RideState): boolean {
  if (['searching', 'assigned', 'arrived', 'in_progress'].includes(ride.status)) return true
  return ride.status === 'completed' && ride.payment_method === 'cash' && ride.payment_status === 'unpaid'
}

const DRIVER_FOUND_KEY = 'bis.driverFoundSeen'

export function driverFoundSeen(rideId: string, storage: Storage = sessionStorage): boolean {
  return storage.getItem(`${DRIVER_FOUND_KEY}:${rideId}`) === '1'
}

export function markDriverFoundSeen(rideId: string, storage: Storage = sessionStorage): void {
  storage.setItem(`${DRIVER_FOUND_KEY}:${rideId}`, '1')
}

import type { RideSummary } from '@/api'
import type { NextAdminDriver, NextDriver, NextOffer, NextRide } from '@/api/next-contract-driver'

export const PICKUP = { latitude: 43.2399, longitude: 76.915 }
export const DROPOFF = { latitude: 43.2185, longitude: 76.9282 }

export function driverFixture(overrides: Partial<NextDriver> = {}): NextDriver {
  return {
    id: 'driver-1',
    full_name: 'Арман Нурланов',
    phone: '+7 701 000 00 00',
    license_number: 'KZ 12345678',
    vehicle: { make: 'Toyota', model: 'Camry', color: 'белый', plate_number: '123 ABC 02', year: 2020, car_class: 'comfort' },
    approval_status: 'approved',
    approved_at: '2026-11-03T05:00:00Z',
    online: false,
    location: { latitude: 43.25, longitude: 76.91 },
    location_updated_at: '2026-11-03T09:00:00Z',
    missing_fields: [],
    rating: { average: 4.9, count: 12 },
    ...overrides,
  }
}

export function offerFixture(overrides: Partial<NextOffer> = {}): NextOffer {
  return {
    id: 'offer-1',
    ride_id: 'ride-1',
    status: 'pending',
    pickup: PICKUP,
    dropoff: DROPOFF,
    distance_m: 10_000,
    duration_s: 1500,
    amount_kzt: 2200,
    currency: 'KZT',
    tariff: 'economy',
    passenger_rating: { average: null, count: 0 },
    created_at: '2026-11-03T09:00:00Z',
    expires_at: '2026-11-03T09:00:30Z',
    ...overrides,
  }
}

export function rideFixture(overrides: Partial<NextRide> = {}): NextRide {
  return {
    id: 'ride-1',
    status: 'assigned',
    passenger_id: 'passenger-1',
    driver_id: 'driver-1',
    quote_id: 'quote-1',
    pickup: PICKUP,
    dropoff: DROPOFF,
    route: {
      distance_m: 10_000,
      duration_s: 1500,
      route_geometry: { type: 'LineString', coordinates: [[PICKUP.longitude, PICKUP.latitude], [DROPOFF.longitude, DROPOFF.latitude]] },
      provider: 'test',
    },
    tariff: 'economy',
    amount_kzt: 2200,
    currency: 'KZT',
    tariff_version: 'v1',
    created_at: '2026-11-03T09:00:00Z',
    updated_at: '2026-11-03T09:00:00Z',
    assigned_at: '2026-11-03T09:00:05Z',
    arrived_at: null,
    started_at: null,
    completed_at: null,
    cancelled_at: null,
    cancel_reason: null,
    payment_method: 'cash',
    payment_status: 'unpaid',
    driver: null,
    ...overrides,
  }
}

export function summaryFixture(overrides: Partial<RideSummary> = {}): RideSummary {
  return {
    id: 'ride-s',
    status: 'completed',
    passenger_id: 'passenger-1',
    driver_id: 'driver-1',
    pickup: PICKUP,
    dropoff: DROPOFF,
    distance_m: 7200,
    duration_s: 1080,
    amount_kzt: 2200,
    currency: 'KZT',
    created_at: '2026-11-03T09:20:00Z',
    updated_at: '2026-11-03T09:40:00Z',
    payment_status: 'paid',
    payment_method: 'kaspi_link',
    ...overrides,
  }
}

export function adminDriverFixture(overrides: Partial<NextAdminDriver> = {}): NextAdminDriver {
  return {
    ...driverFixture({ approval_status: 'pending', approved_at: null }),
    username: 'arman',
    created_at: '2026-11-03T04:00:00Z',
    approved_by: null,
    ...overrides,
  } as NextAdminDriver
}

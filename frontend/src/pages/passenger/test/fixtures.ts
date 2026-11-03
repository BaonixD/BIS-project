import type { DriverCard, Quote, RideDetails } from '@/api'

export const PICKUP = { latitude: 43.2545, longitude: 76.936 }
export const DROPOFF = { latitude: 43.21834, longitude: 76.92763 }

export const ROUTE = {
  distance_m: 10_000,
  duration_s: 1500,
  provider: 'openrouteservice',
  route_geometry: { type: 'LineString', coordinates: [[PICKUP.longitude, PICKUP.latitude], [DROPOFF.longitude, DROPOFF.latitude]] },
}

export const QUOTE: Quote = {
  quote_id: 'quote-1',
  pickup: PICKUP,
  dropoff: DROPOFF,
  route: ROUTE,
  options: [
    { tariff: 'economy', amount_kzt: 2200 },
    { tariff: 'comfort', amount_kzt: 2925 },
    { tariff: 'comfort_plus', amount_kzt: 3650 },
    { tariff: 'business', amount_kzt: 4800 },
  ],
  currency: 'KZT',
  tariff_version: 'edu-v2',
  kaspi_payment_url: 'https://pay.kaspi.kz/pay/test',
  created_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 600_000).toISOString(),
} as Quote

export const DRIVER: DriverCard = {
  full_name: 'Арман Нурланов',
  phone: '+77011234567',
  vehicle: { make: 'Toyota', model: 'Camry', color: 'серо-синий', plate_number: '123 ABC 02', car_class: 'comfort' },
  location: { latitude: 43.266, longitude: 76.936 },
  location_updated_at: new Date().toISOString(),
  rating: { average: 4.9, count: 10 },
}

export function makeRide(overrides: Partial<RideDetails> = {}): RideDetails {
  const now = new Date().toISOString()
  return {
    id: 'ride-1',
    status: 'searching',
    passenger_id: 'p1',
    driver_id: null,
    quote_id: 'quote-1',
    pickup: PICKUP,
    dropoff: DROPOFF,
    route: ROUTE,
    tariff: 'economy',
    amount_kzt: 2200,
    currency: 'KZT',
    tariff_version: 'edu-v2',
    created_at: now,
    updated_at: now,
    assigned_at: null,
    arrived_at: null,
    started_at: null,
    completed_at: null,
    cancelled_at: null,
    cancel_reason: null,
    payment_method: 'kaspi_link',
    payment_status: 'unpaid',
    driver: null,
    my_rating: null,
    ...overrides,
  } as RideDetails
}

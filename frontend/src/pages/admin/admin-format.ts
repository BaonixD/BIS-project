import type { RideStatus, RideSummary, UserRole } from '@/api'
import type { NextAdminDriver } from '@/api/driver-types'
import type { StatusTone } from '@/components/ui-kit'
import { formatMoney } from '@/lib/format'

/** «Арман Нурланов» → «Арман Н.». */
export function shortName(fullName: string): string {
  const [first, ...rest] = fullName.trim().split(/\s+/)
  const last = rest.at(-1)
  return last ? `${first} ${last.charAt(0)}.` : (first ?? '')
}

const STATUS_PILL: Record<RideStatus, { tone: StatusTone; label: string }> = {
  searching: { tone: 'inverse', label: 'Поиск' },
  assigned: { tone: 'info', label: 'Назначена' },
  arrived: { tone: 'info', label: 'На месте' },
  in_progress: { tone: 'info', label: 'В пути' },
  completed: { tone: 'success', label: 'Завершена' },
  cancelled: { tone: 'neutral', label: 'Отменена' },
  no_driver: { tone: 'neutral', label: 'Нет водителя' },
}

export function rideStatusPill(status: RideStatus) {
  return STATUS_PILL[status]
}

const CLOSED: RideStatus[] = ['cancelled', 'no_driver']

/** Desktop «СУММА»: no amount for a cancelled ride. */
export function amountCell(ride: RideSummary): string {
  return CLOSED.includes(ride.status) ? '—' : formatMoney(ride.amount_kzt)
}

/** Desktop «ОПЛАТА»: «Наличные», «Kaspi · оплачено», «—» while searching or after a cancel. */
export function paymentCell(ride: RideSummary): string {
  if (!ride.payment_method || ride.status === 'searching' || CLOSED.includes(ride.status)) return '—'
  const method = ride.payment_method === 'kaspi_link' ? 'Kaspi' : 'Наличные'
  if (ride.payment_status === 'paid') return `${method} · оплачено`
  if (ride.payment_status === 'refunded') return `${method} · возврат`
  return method
}

/** Mobile row: «Айгерим · Арман Н. · 2 200 ₸», «Дана · ищем водителя», «Мадина · —». */
export function rideSubtitle(ride: RideSummary, passenger: string, driver: string | null): string {
  if (driver) return `${passenger} · ${driver} · ${formatMoney(ride.amount_kzt)}`
  if (ride.status === 'searching') return `${passenger} · ищем водителя`
  return `${passenger} · —`
}

export const ROLE_PILL: Record<UserRole, { tone: StatusTone; label: string }> = {
  passenger: { tone: 'info', label: 'пассажир' },
  driver: { tone: 'inverse', label: 'водитель' },
  admin: { tone: 'neutral', label: 'админ' },
}

/** «Toyota Camry · белый · 123ABC02». */
export function vehicleLine(driver: Pick<NextAdminDriver, 'vehicle'>): string {
  const vehicle = driver.vehicle
  return vehicle ? `${vehicle.make} ${vehicle.model} · ${vehicle.color} · ${vehicle.plate_number}` : 'Машина не указана'
}

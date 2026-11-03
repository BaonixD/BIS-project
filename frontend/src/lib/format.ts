import type { Coordinates } from '@/api'

const TIME_ZONE = 'Asia/Almaty'

const moneyFormat = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'KZT',
  currencyDisplay: 'narrowSymbol',
  maximumFractionDigits: 0,
})

const dateTimeFormat = new Intl.DateTimeFormat('ru-RU', {
  timeZone: TIME_ZONE,
  dateStyle: 'short',
  timeStyle: 'short',
})

export function formatMoney(amountKzt: number): string {
  return moneyFormat.format(amountKzt)
}

export function formatDistance(distanceM: number): string {
  if (distanceM < 1000) return `${distanceM} м`
  return `${(distanceM / 1000).toFixed(1).replace('.', ',')} км`
}

export function formatDuration(durationS: number): string {
  const minutes = Math.max(1, Math.round(durationS / 60))
  if (minutes < 60) return `${minutes} мин`
  return `${Math.floor(minutes / 60)} ч ${minutes % 60} мин`
}

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTimeFormat.format(new Date(iso)) : '—'
}

export function formatCoordinates(point: Coordinates): string {
  return `${point.latitude.toFixed(5)}, ${point.longitude.toFixed(5)}`
}

export function minutesSince(iso: string, now = Date.now()): number {
  return Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60_000))
}

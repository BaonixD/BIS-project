import { t, getIntlLocale } from '@/i18n/core'
import type { Coordinates } from '@/api'
const TIME_ZONE = 'Asia/Almaty'
const moneyFormat = () =>
  new Intl.NumberFormat(getIntlLocale(), {
    style: 'currency',
    currency: 'KZT',
    currencyDisplay: 'narrowSymbol',
    maximumFractionDigits: 0,
  })
const dateTimeFormat = () =>
  new Intl.DateTimeFormat(getIntlLocale(), {
    timeZone: TIME_ZONE,
    dateStyle: 'short',
    timeStyle: 'short',
  })
export function formatMoney(amountKzt: number): string {
  return moneyFormat().format(amountKzt)
}
export function formatDistance(distanceM: number): string {
  if (distanceM < 1000) return t('{p0} м', { p0: distanceM })
  return t('{p0} км', {
    p0: new Intl.NumberFormat(getIntlLocale(), {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(distanceM / 1000),
  })
}
export function formatDuration(durationS: number): string {
  const minutes = Math.max(1, Math.round(durationS / 60))
  if (minutes < 60) return t('{p0} мин', { p0: minutes })
  return t('{p0} ч {p1} мин', { p0: Math.floor(minutes / 60), p1: minutes % 60 })
}
export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTimeFormat().format(new Date(iso)) : '—'
}
export function formatCoordinates(point: Coordinates): string {
  return `${point.latitude.toFixed(5)}, ${point.longitude.toFixed(5)}`
}
export function minutesSince(iso: string, now = Date.now()): number {
  return Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60000))
}

import { dateFormatter } from '@/i18n/date'
import { t, getLocale } from '@/i18n/core'
import type { RideSummary } from '@/api'
import type { StatusTone } from '@/components/ui-kit'
const TIME_ZONE = 'Asia/Almaty'
const DAY_MS = 24 * 60 * 60 * 1000
function almatyParts(date: Date) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: TIME_ZONE,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric',
    second: 'numeric',
    hourCycle: 'h23',
  }).formatToParts(date)
  const value = (type: string) => Number(parts.find((part) => part.type === type)?.value)
  return {
    year: value('year'),
    month: value('month'),
    day: value('day'),
    hour: value('hour'),
    minute: value('minute'),
    second: value('second'),
  }
}
/** Midnight in Almaty for the day containing `now`, as a UTC instant. */
export function almatyDayStart(now: Date): Date {
  const p = almatyParts(now)
  const wallClockAsUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second)
  const offsetMs = wallClockAsUtc - Math.floor(now.getTime() / 1000) * 1000
  return new Date(Date.UTC(p.year, p.month - 1, p.day) - offsetMs)
}
export type HistoryPeriod = 'today' | 'week' | 'all'
/** `created_from` for the history filter: today, the last 7 days (with today) or everything. */
export function periodStart(period: HistoryPeriod, now: Date): string | undefined {
  if (period === 'all') return undefined
  const start = almatyDayStart(now).getTime() - (period === 'week' ? 6 * DAY_MS : 0)
  return new Date(start).toISOString()
}
export interface ShiftStats {
  rides: number
  earnedKzt: number
  drivingS: number
}
/** Completed rides only: their count, the fares and the time on the road. */
export function summarizeShift(rides: readonly RideSummary[]): ShiftStats {
  const completed = rides.filter((ride) => ride.status === 'completed')
  return {
    rides: completed.length,
    earnedKzt: completed.reduce((sum, ride) => sum + ride.amount_kzt, 0),
    drivingS: completed.reduce((sum, ride) => sum + ride.duration_s, 0),
  }
}
/** «45 мин», «2 ч 15 мин», «1 ч». */
export function formatSpan(seconds: number): string {
  const minutes = Math.max(0, Math.floor(seconds / 60))
  if (minutes < 60) return t('{p0} мин', { p0: minutes })
  const rest = minutes % 60
  return rest
    ? t('{p0} ч {p1} мин', { p0: Math.floor(minutes / 60), p1: rest })
    : t('{p0} ч', { p0: Math.floor(minutes / 60) })
}
export function ridesWord(count: number): string {
  if (getLocale() === 'en') return count === 1 ? 'ride' : 'rides'
  if (getLocale() === 'kk') return 'сапар'
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return t('поездка')
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return t('поездки')
  return t('поездок')
}
const timeFormat = () =>
  dateFormatter({
    timeZone: TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
  })
const dayFormat = () => dateFormatter({ timeZone: TIME_ZONE, day: 'numeric', month: 'short' })
/** «14:20» today, «2 нояб., 14:20» earlier. */
export function formatRideTime(iso: string, now: Date): string {
  const date = new Date(iso)
  const time = timeFormat().format(date)
  return date >= almatyDayStart(now) ? time : `${dayFormat().format(date)}, ${time}`
}
/** The pill of a history row: whether the money is in. */
export function ridePill(ride: RideSummary): {
  tone: StatusTone
  label: string
} {
  switch (ride.status) {
    case 'completed':
      if (ride.payment_status === 'paid') {
        return {
          tone: 'success',
          label: ride.payment_method === 'cash' ? t('Получено') : t('Оплачено'),
        }
      }
      if (ride.payment_status === 'refunded') return { tone: 'neutral', label: t('Возврат') }
      return { tone: 'warning', label: t('Ожидает') }
    case 'cancelled':
    case 'no_driver':
      return { tone: 'neutral', label: t('Отменена') }
    case 'in_progress':
      return { tone: 'info', label: t('В пути') }
    case 'arrived':
      return { tone: 'info', label: t('На месте') }
    default:
      return { tone: 'info', label: t('Назначена') }
  }
}

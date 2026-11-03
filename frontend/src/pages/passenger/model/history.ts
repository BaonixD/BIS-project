import type { RideStatus, RideSummary } from '@/api'
import type { StatusTone } from '@/components/ui-kit'
import { RIDE_STATUS_LABELS } from '@/lib/labels'
import { formatClock, formatPrice, historyDayLabel } from './format'
import { PAYMENT_LABELS } from './order'

export type HistoryFilter = 'all' | 'completed' | 'cancelled'

export const HISTORY_FILTERS: { id: HistoryFilter; label: string }[] = [
  { id: 'all', label: 'Все' },
  { id: 'completed', label: 'Завершённые' },
  { id: 'cancelled', label: 'Отменённые' },
]

export function filterStatuses(filter: HistoryFilter): RideStatus[] | undefined {
  if (filter === 'completed') return ['completed']
  if (filter === 'cancelled') return ['cancelled', 'no_driver']
  return undefined
}

type RideState = Pick<RideSummary, 'status' | 'payment_status'>

/** History/details pill (Figma 5:550, 24:708). */
export function ridePill(ride: RideState): { tone: StatusTone; text: string } {
  if (ride.payment_status === 'refunded') return { tone: 'info', text: 'Возвращено' }
  switch (ride.status) {
    case 'completed':
      return ride.payment_status === 'paid' ? { tone: 'success', text: 'Оплачено' } : { tone: 'warning', text: 'Не оплачено' }
    case 'cancelled':
      return { tone: 'neutral', text: 'Отменена' }
    case 'no_driver':
      return { tone: 'neutral', text: 'Нет водителя' }
    default:
      return { tone: 'inverse', text: RIDE_STATUS_LABELS[ride.status] }
  }
}

export function isUnfulfilled(status: RideStatus): boolean {
  return status === 'cancelled' || status === 'no_driver'
}

export function historyPrice(ride: Pick<RideSummary, 'status' | 'amount_kzt'>): string {
  return isUnfulfilled(ride.status) ? '—' : formatPrice(ride.amount_kzt)
}

/** «14:20 · Наличные»; only the time for a ride that did not happen. */
export function historyMeta(ride: Pick<RideSummary, 'status' | 'created_at' | 'payment_method'>): string {
  const time = formatClock(ride.created_at)
  if (isUnfulfilled(ride.status) || !ride.payment_method) return time
  return `${time} · ${PAYMENT_LABELS[ride.payment_method]}`
}

/** Rides grouped by day label, keeping the API order (newest first). */
export function groupByDay<T extends Pick<RideSummary, 'created_at'>>(rides: T[], now = Date.now()): [string, T[]][] {
  const groups = new Map<string, T[]>()
  for (const ride of rides) {
    const label = historyDayLabel(ride.created_at, now)
    groups.set(label, [...(groups.get(label) ?? []), ride])
  }
  return [...groups.entries()]
}

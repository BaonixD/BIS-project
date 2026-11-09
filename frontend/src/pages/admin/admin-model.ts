import { useSearchParams } from 'react-router'
import type { RideSummary } from '@/api'

export const ADMIN_PAGE_SIZE = 20

export function useAdminFilters() {
  const [params, setParams] = useSearchParams()
  const offsetValue = Number(params.get('offset') ?? 0)
  const offset =
    Number.isSafeInteger(offsetValue) && offsetValue >= 0 && offsetValue <= 10_000_000
      ? offsetValue
      : 0
  const update = (values: Record<string, string>, paging = false) => {
    setParams((previous) => {
      const next = new URLSearchParams(previous)
      if (!paging) next.delete('offset')
      Object.entries(values).forEach(([key, value]) =>
        value ? next.set(key, value) : next.delete(key),
      )
      return next
    })
  }
  return { params, offset, update, reset: () => setParams({}) }
}

export const adminDate = (value: string | null | undefined) =>
  value
    ? new Intl.DateTimeFormat('ru-RU', {
        timeZone: 'Asia/Almaty',
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(new Date(value))
    : '—'

export function adminPayment(ride: Pick<RideSummary, 'payment_method' | 'payment_status'>) {
  const method =
    ride.payment_method === 'kaspi_link'
      ? 'Kaspi'
      : ride.payment_method === 'cash'
        ? 'Наличные'
        : '—'
  const status =
    ride.payment_status === 'paid'
      ? 'оплачено'
      : ride.payment_status === 'refunded'
        ? 'возврат'
        : 'не оплачено'
  return `${method} · ${status}`
}

export function periodFrom(period: string): string | undefined {
  if (!['today', 'week', 'month'].includes(period)) return undefined
  const localDate = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Almaty',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
  const start = new Date(`${localDate}T00:00:00+05:00`)
  if (period === 'week') start.setUTCDate(start.getUTCDate() - 6)
  if (period === 'month') start.setUTCDate(start.getUTCDate() - 29)
  return start.toISOString()
}

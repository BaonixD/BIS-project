import type { RideDetails } from '@/api'
import { formatPrice } from '@/pages/passenger/model/format'
import { isPaidKaspi } from '@/pages/passenger/model/ride-screen'

type PaymentInfo = Pick<RideDetails, 'payment_method' | 'payment_status' | 'amount_kzt' | 'status'>

/** Drop-off row caption on the tracking sheets: «Куда · наличные», «Куда · Kaspi · оплачено». */
export function dropoffCaption(ride: PaymentInfo, { searching = false } = {}): string {
  if (searching) return isPaidKaspi(ride) ? 'Куда · Kaspi · списано' : 'Куда'
  if (ride.payment_method === 'cash') return 'Куда · наличные'
  return isPaidKaspi(ride) ? 'Куда · Kaspi · оплачено' : 'Куда · Kaspi'
}

/** Figma 24:628 text of «Отменить поездку?». */
export function cancelText(ride: PaymentInfo): string {
  const hasDriver = ride.status === 'assigned' || ride.status === 'arrived'
  const lead = hasDriver ? 'Водитель уже едет к вам.' : 'Водитель ещё не найден.'
  if (isPaidKaspi(ride)) return `${lead} Оплата Kaspi ${formatPrice(ride.amount_kzt)} вернётся автоматически.`
  return hasDriver ? `${lead} Отмена бесплатная.` : `${lead} Деньги не списаны.`
}

/** Payment line of «В пути» (24:549) and receipts. */
export function paymentLine(ride: PaymentInfo): string {
  if (ride.payment_method === 'cash') return ride.payment_status === 'paid' ? 'Наличные · оплачено' : 'Наличные · водителю'
  if (ride.payment_status === 'paid') return 'Kaspi · оплачено'
  if (ride.payment_status === 'refunded') return 'Kaspi · возвращено'
  return 'Kaspi · при назначении'
}

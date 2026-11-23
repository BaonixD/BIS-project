import { t } from '@/i18n/core'
import { moneyDue } from '@/lib/money'
import type { RideDetails } from '@/api'
import { formatPrice } from '@/pages/passenger/model/format'
import { isPaidKaspi } from '@/pages/passenger/model/ride-screen'
type PaymentInfo = Pick<
  RideDetails,
  'payment_method' | 'payment_status' | 'amount_kzt' | 'bonus_kzt' | 'status'
>
/** Drop-off row caption on the tracking sheets: «Куда · наличные», «Куда · Kaspi · оплачено». */
export function dropoffCaption(ride: PaymentInfo, { searching = false } = {}): string {
  if (searching) return isPaidKaspi(ride) ? t('Куда · Kaspi · списано') : t('Куда')
  if (ride.payment_method === 'cash') return t('Куда · наличные')
  return isPaidKaspi(ride) ? t('Куда · Kaspi · оплачено') : t('Куда · Kaspi')
}
/** Figma 24:628 text of «Отменить поездку?». */
export function cancelText(ride: PaymentInfo): string {
  const hasDriver = ride.status === 'assigned' || ride.status === 'arrived'
  const lead = hasDriver ? t('Водитель уже едет к вам.') : t('Водитель ещё не найден.')
  if (isPaidKaspi(ride))
    return t('{p0} Оплата Kaspi {p1} вернётся автоматически.', {
      p0: lead,
      p1: formatPrice(moneyDue(ride)),
    })
  return hasDriver
    ? t('{p0} Отмена бесплатная.', { p0: lead })
    : t('{p0} Деньги не списаны.', { p0: lead })
}
/** Payment line of «В пути» (24:549) and receipts. */
export function paymentLine(ride: PaymentInfo): string {
  if (ride.payment_method === 'cash')
    return ride.payment_status === 'paid' ? t('Наличные · оплачено') : t('Наличные · водителю')
  if (ride.payment_status === 'paid') return t('Kaspi · оплачено')
  if (ride.payment_status === 'refunded') return t('Kaspi · возвращено')
  return t('Kaspi · при назначении')
}

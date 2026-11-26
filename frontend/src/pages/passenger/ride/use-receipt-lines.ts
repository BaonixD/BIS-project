import type { DriverCard, RideDetails } from '@/api'
import { driverLine, usePlaceTitle } from '@/components/passenger/ride-text'
import { usePayment } from '@/hooks/use-payment'
import { t } from '@/i18n/core'
import { moneyDue } from '@/lib/money'
import { formatPrice, formatRideDate } from '@/pages/passenger/model/format'
import { TARIFF_LABELS } from '@/pages/passenger/model/order'
import { receiptNumber } from '@/pages/passenger/model/receipt'

export type ReceiptLine = [string, string]

/** Lines of the receipt; `full` adds the trip itself for the receipt page and sharing. */
export function useReceiptLines(
  ride: RideDetails,
  driver: DriverCard | null,
  full: boolean,
): { lines: ReceiptLine[]; paid: number; refunded: boolean } {
  const payment = usePayment(ride.id, {
    enabled: ride.payment_status !== 'unpaid',
  }).data
  const from = usePlaceTitle(ride.pickup)
  const to = usePlaceTitle(ride.dropoff)
  const paidAt = payment?.paid_at ?? ride.assigned_at ?? ride.updated_at
  const refunded = (payment?.status ?? ride.payment_status) === 'refunded'
  const kaspi = ride.payment_method === 'kaspi_link'
  const lines: ReceiptLine[] = [
    [t('№ чека'), receiptNumber(ride.id)],
    [t('Дата'), formatRideDate(paidAt)],
    [t('Способ'), kaspi ? 'Kaspi' : t('Наличные')],
  ]
  if (full) {
    lines.push([t('Тариф'), TARIFF_LABELS()[ride.tariff]])
    if (from && to) lines.push([t('Маршрут'), `${from} → ${to}`])
    if (driver) lines.push([t('Водитель'), driverLine(driver) ?? '—'])
    if (ride.bonus_kzt > 0) {
      lines.push([t('Стоимость поездки'), formatPrice(ride.amount_kzt)])
      lines.push([t('Бонусами'), `−${formatPrice(ride.bonus_kzt)}`])
    }
    if (refunded && payment?.refunded_at)
      lines.push([t('Возврат'), formatRideDate(payment.refunded_at)])
  }
  return { lines, paid: payment?.amount_kzt ?? moneyDue(ride), refunded }
}

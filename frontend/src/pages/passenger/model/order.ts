import type { PaymentMethod, Quote } from '@/api'
import type { RideCreateRequest, Tariff } from '@/api/passenger-types'
import type { TariffOption } from '@/components/ui-kit'
import { formatPrice } from './format'

export const TARIFF_LABELS: Record<Tariff, string> = {
  economy: 'Эконом',
  comfort: 'Комфорт',
  comfort_plus: 'Комфорт+',
  business: 'Бизнес',
}

export const PAYMENT_LABELS: Record<PaymentMethod, string> = {
  cash: 'Наличные',
  kaspi_link: 'Kaspi',
}

export function orderButtonLabel(tariff: Tariff, method: PaymentMethod): string {
  return `Заказать ${TARIFF_LABELS[tariff]} · ${PAYMENT_LABELS[method]}`
}

export function tariffOptions(quote: Pick<Quote, 'options'>): TariffOption[] {
  return quote.options.map((option) => ({
    id: option.tariff,
    name: TARIFF_LABELS[option.tariff],
    price: formatPrice(option.amount_kzt),
  }))
}

export function buildRideOrder({
  quoteId,
  tariff,
  paymentMethod,
}: {
  quoteId: string
  tariff: Tariff
  paymentMethod: PaymentMethod
}): RideCreateRequest {
  return { quote_id: quoteId, payment_method: paymentMethod, tariff }
}

export type KaspiCheck = 'not_needed' | 'opened' | 'unavailable'

/**
 * Kaspi is paid through the owner's link: open it in a new tab before the order is created,
 * still inside the click handler so the browser does not block the popup.
 * Opening the link confirms nothing; the ride is counted as paid when a driver is assigned.
 */
export function openKaspiLink(
  method: PaymentMethod,
  url: string | null,
  open: (url: string, target: string, features: string) => unknown = (...args) => window.open(...args),
): KaspiCheck {
  if (method !== 'kaspi_link') return 'not_needed'
  if (!url) return 'unavailable'
  open(url, '_blank', 'noopener,noreferrer')
  return 'opened'
}

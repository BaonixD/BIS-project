import { t } from '@/i18n/core'

/** «TT-3F9A12BC»: short, stable and readable aloud to support. */
export function receiptNumber(rideId: string): string {
  return `TT-${rideId.replace(/-/g, '').slice(0, 8).toUpperCase()}`
}

/** Plain text for «Поделиться»: what a person would copy from a paper receipt. */
export function receiptText(lines: [string, string][]): string {
  return [t('TulparTaxi · Чек об оплате'), ...lines.map(([label, value]) => `${label}: ${value}`)]
    .filter(Boolean)
    .join('\n')
}

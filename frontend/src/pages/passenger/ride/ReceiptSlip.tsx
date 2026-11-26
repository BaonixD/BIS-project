import type { ReactNode } from 'react'
import type { DriverCard, RideDetails } from '@/api'
import { BrandMark } from '@/components/common/BrandLogo'
import { KazakhMotif } from '@/components/common/Ornament'
import { StatusPill } from '@/components/ui-kit'
import { t, useLocale } from '@/i18n/core'
import { cn } from '@/lib/utils'
import { formatPrice } from '@/pages/passenger/model/format'
import { useReceiptLines } from './use-receipt-lines'

/** A paper slip: printed from the top when it appears, torn at the bottom. */
export function ReceiptSlip({
  ride,
  driver,
  full = false,
  footer,
  className,
}: {
  ride: RideDetails
  driver: DriverCard | null
  full?: boolean
  footer?: ReactNode
  className?: string
}) {
  useLocale()
  const { lines, paid, refunded } = useReceiptLines(ride, driver, full)
  return (
    <section
      aria-label={t('Чек об оплате')}
      className={cn(
        'receipt-edge relative w-full shrink-0 overflow-hidden rounded-t-[20px] bg-bg-canvas px-5 pt-5 text-left shadow-card motion-safe:animate-receipt-print',
        className,
      )}
    >
      <span aria-hidden className="absolute inset-x-0 top-0 h-1 bg-accent-kaspi" />
      <div className="flex items-center gap-3">
        <BrandMark className="size-9" />
        <div className="flex min-w-0 flex-1 flex-col">
          <p className="text-callout text-text-primary">{t('Чек об оплате')}</p>
          <p className="text-caption text-text-secondary">TulparTaxi · {t('Алматы')}</p>
        </div>
        <StatusPill tone={refunded ? 'info' : 'success'}>
          {refunded ? t('Возвращено') : t('Оплачено')}
        </StatusPill>
      </div>
      <p className="mt-4 text-center text-display text-text-primary">{formatPrice(paid)}</p>
      <div aria-hidden className="my-4 border-t border-dashed border-border-default" />
      <dl className="flex flex-col gap-2.5 text-callout">
        {lines.map(([label, value]) => (
          <div key={label} className="flex items-start gap-3">
            <dt className="shrink-0 text-text-secondary">{label}</dt>
            <dd className="min-w-0 flex-1 text-right break-words text-text-primary tabular-nums">
              {value}
            </dd>
          </div>
        ))}
      </dl>
      <div aria-hidden className="my-4 border-t border-dashed border-border-default" />
      <div className="flex items-center gap-2 text-caption text-text-secondary">
        <KazakhMotif className="h-3.5 w-[18px] text-brand-gold" />
        <p className="flex-1">
          {t('Учебная оплата — реальные деньги не списываются. Рахмет, что вы с нами!')}
        </p>
      </div>
      {footer}
    </section>
  )
}

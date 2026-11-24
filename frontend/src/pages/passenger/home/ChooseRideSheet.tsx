import { t, useLocale } from '@/i18n/core'
import { CircleDot, Gift, MapPin } from 'lucide-react'
import type { PaymentMethod, Quote } from '@/api'
import type { Tariff } from '@/api/passenger-types'
import { Button, PaymentMethodPicker, Skeleton, TariffCarousel } from '@/components/ui-kit'
import routeRail from '@/assets/passenger/route-rail.svg'
import { orderButtonLabel, tariffOptions } from '@/pages/passenger/model/order'
import { formatPrice } from '@/pages/passenger/model/format'
import { cn } from '@/lib/utils'
interface ChooseRideSheetProps {
  pickupTitle: string
  dropoffTitle: string
  quote: Quote | undefined
  tariff: Tariff
  onTariffChange: (tariff: Tariff) => void
  paymentMethod: PaymentMethod
  onPaymentMethodChange: (method: PaymentMethod) => void
  bonusBalance: number
  useBonus: boolean
  onUseBonusChange: (use: boolean) => void
  ordering: boolean
  error: string | null
  onOrder: () => void
  onEdit: (target: 'pickup' | 'dropoff') => void
}
/** Figma 17:718 «RouteSummary»: rail, two addresses, distance and time. */
function RouteSummary({
  pickupTitle,
  dropoffTitle,
}: Pick<ChooseRideSheetProps, 'pickupTitle' | 'dropoffTitle'>) {
  useLocale()
  return (
    <div className="flex w-full items-center gap-3 overflow-hidden rounded-lg bg-bg-subtle px-4 py-3 lg:hidden">
      <img src={routeRail} width={12} height={40} alt="" aria-hidden className="block shrink-0 dark:invert" />
      <div className="flex min-w-0 flex-1 flex-col gap-1.5 text-body-medium text-text-primary">
        <p className="truncate">{pickupTitle}</p>
        <p className="truncate">{dropoffTitle}</p>
      </div>
    </div>
  )
}
/** Desktop 7:74: the two points as fields under «Заказать поездку». */
function DesktopPoints({
  pickupTitle,
  dropoffTitle,
  onEdit,
}: Pick<ChooseRideSheetProps, 'pickupTitle' | 'dropoffTitle' | 'onEdit'>) {
  useLocale()
  const field = (Icon: typeof MapPin, text: string, target: 'pickup' | 'dropoff') => (
    <button
      type="button"
      onClick={() => onEdit(target)}
      className="flex h-14 w-full items-center gap-3 rounded-md bg-bg-subtle px-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
    >
      <Icon className="size-6 shrink-0 text-text-primary" strokeWidth={2} aria-hidden />
      <span className="min-w-0 flex-1 truncate text-body-medium text-text-secondary">{text}</span>
    </button>
  )
  return (
    <>
      <h1 className="hidden w-full text-title text-text-primary lg:block">
        {t('Заказать поездку')}
      </h1>
      <div className="hidden w-full flex-col gap-2 lg:flex">
        {field(CircleDot, pickupTitle, 'pickup')}
        {field(MapPin, dropoffTitle, 'dropoff')}
      </div>
    </>
  )
}
/** Bonuses cover at most half of the price (the server applies the same limit). */
function BonusToggle({
  balance,
  price,
  checked,
  onChange,
}: {
  balance: number
  price: number | undefined
  checked: boolean
  onChange: (use: boolean) => void
}) {
  useLocale()
  const usable = price === undefined ? 0 : Math.min(balance, Math.floor(price / 2))
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn(
        'flex w-full items-center gap-3 rounded-[10px] border px-3 py-2.5 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-bg-inverse',
        checked ? 'border-brand-sky bg-brand-sky-soft' : 'border-border-default bg-bg-canvas',
      )}
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-brand-gold/20 text-text-primary">
        <Gift className="size-5" aria-hidden />
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-callout text-text-primary">
          {checked && usable > 0
            ? t('Бонусы: −{p0}', { p0: formatPrice(usable) })
            : t('Оплатить бонусами')}
        </span>
        <span className="truncate text-caption text-text-secondary">
          {t('Доступно {p0} · до половины поездки', { p0: formatPrice(balance) })}
        </span>
      </span>
      <span
        aria-hidden
        className={cn(
          'flex h-6 w-10 shrink-0 items-center rounded-full p-0.5 transition-colors',
          checked ? 'bg-brand-sky-ink' : 'bg-bg-muted',
        )}
      >
        <span
          className={cn(
            'size-5 rounded-full bg-bg-canvas shadow-card transition-transform motion-reduce:transition-none',
            checked && 'translate-x-4',
          )}
        />
      </span>
    </button>
  )
}

const NOTE = (): Record<PaymentMethod, string> => ({
  kaspi_link: t('Деньги спишутся, когда найдётся водитель. Отмена до этого — бесплатно.'),
  cash: t('Оплата наличными водителю после поездки. Отмена до назначения — бесплатно.'),
})
/** Figma Choose ride 4:327 (mobile) and the Desktop 7:72 panel. */
export function ChooseRideSheet(props: ChooseRideSheetProps) {
  useLocale()
  const {
    quote,
    tariff,
    onTariffChange,
    paymentMethod,
    onPaymentMethodChange,
    bonusBalance,
    useBonus,
    onUseBonusChange,
    ordering,
    error,
    onOrder,
  } = props
  return (
    <>
      <RouteSummary {...props} />
      <DesktopPoints {...props} />
      {quote ? (
        <TariffCarousel
          options={tariffOptions(quote)}
          value={tariff}
          onChange={(id) => onTariffChange(id as Tariff)}
          className="shrink-0"
        />
      ) : (
        <div
          className="flex w-full shrink-0 gap-2.5 overflow-hidden"
          aria-busy
          aria-label={t('Считаем цену')}
        >
          <Skeleton className="h-20 w-[212px] shrink-0 rounded-[10px]" />
          <Skeleton className="h-20 w-[212px] shrink-0 rounded-[10px]" />
        </div>
      )}
      <PaymentMethodPicker value={paymentMethod} onChange={onPaymentMethodChange} />
      {bonusBalance > 0 && (
        <BonusToggle
          balance={bonusBalance}
          price={quote?.options.find((option) => option.tariff === tariff)?.amount_kzt}
          checked={useBonus}
          onChange={onUseBonusChange}
        />
      )}
      <Button className="w-full" loading={ordering} disabled={!quote} onClick={onOrder}>
        {orderButtonLabel(tariff, paymentMethod)}
      </Button>
      {error && (
        <p role="alert" className="w-full text-center text-caption text-accent-danger">
          {error}
        </p>
      )}
      <p className="w-full text-center text-caption text-text-secondary lg:text-left">
        <span className="lg:hidden">{NOTE()[paymentMethod]}</span>
        <span className="hidden lg:inline">
          {paymentMethod === 'kaspi_link'
            ? t('Деньги спишутся, когда найдётся водитель')
            : t('Наличные — водителю после поездки')}
          {t(' · точки можно выбрать кликом по карте')}
        </span>
      </p>
    </>
  )
}

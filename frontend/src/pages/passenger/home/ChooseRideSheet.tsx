import { CircleDot, MapPin } from 'lucide-react'
import type { PaymentMethod, Quote } from '@/api'
import type { Tariff } from '@/api/passenger-types'
import { Button, PaymentMethodPicker, Skeleton, TariffCarousel } from '@/components/ui-kit'
import routeRail from '@/assets/passenger/route-rail.svg'
import { formatKmCompact, formatMinutes } from '@/pages/passenger/model/format'
import { orderButtonLabel, tariffOptions } from '@/pages/passenger/model/order'

interface ChooseRideSheetProps {
  pickupTitle: string
  dropoffTitle: string
  quote: Quote | undefined
  tariff: Tariff
  onTariffChange: (tariff: Tariff) => void
  paymentMethod: PaymentMethod
  onPaymentMethodChange: (method: PaymentMethod) => void
  ordering: boolean
  error: string | null
  onOrder: () => void
  onEdit: (target: 'pickup' | 'dropoff') => void
}

/** Figma 17:718 «RouteSummary»: rail, two addresses, distance and time. */
function RouteSummary({ pickupTitle, dropoffTitle, quote }: Pick<ChooseRideSheetProps, 'pickupTitle' | 'dropoffTitle' | 'quote'>) {
  return (
    <div className="flex w-full items-center gap-3 overflow-hidden rounded-lg bg-bg-subtle px-4 py-3 lg:hidden">
      <img src={routeRail} width={12} height={40} alt="" aria-hidden className="block shrink-0" />
      <div className="flex min-w-0 flex-1 flex-col gap-1.5 text-body-medium text-text-primary">
        <p className="truncate">{pickupTitle}</p>
        <p className="truncate">{dropoffTitle}</p>
      </div>
      {quote ? (
        <p className="shrink-0 text-caption whitespace-nowrap text-text-secondary">
          {formatKmCompact(quote.route.distance_m)} · {formatMinutes(quote.route.duration_s)}
        </p>
      ) : (
        <Skeleton className="h-4 w-20" />
      )}
    </div>
  )
}

/** Desktop 7:74: the two points as fields under «Заказать поездку». */
function DesktopPoints({ pickupTitle, dropoffTitle, onEdit }: Pick<ChooseRideSheetProps, 'pickupTitle' | 'dropoffTitle' | 'onEdit'>) {
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
      <h1 className="hidden w-full text-title text-text-primary lg:block">Заказать поездку</h1>
      <div className="hidden w-full flex-col gap-2 lg:flex">
        {field(CircleDot, pickupTitle, 'pickup')}
        {field(MapPin, dropoffTitle, 'dropoff')}
      </div>
    </>
  )
}

const NOTE: Record<PaymentMethod, string> = {
  kaspi_link: 'Деньги спишутся, когда найдётся водитель. Отмена до этого — бесплатно.',
  cash: 'Оплата наличными водителю после поездки. Отмена до назначения — бесплатно.',
}

/** Figma Choose ride 4:327 (mobile) and the Desktop 7:72 panel. */
export function ChooseRideSheet(props: ChooseRideSheetProps) {
  const { quote, tariff, onTariffChange, paymentMethod, onPaymentMethodChange, ordering, error, onOrder } = props
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
        <div className="flex w-full shrink-0 gap-2.5 overflow-hidden" aria-busy aria-label="Считаем цену">
          <Skeleton className="h-20 w-[212px] shrink-0 rounded-[10px]" />
          <Skeleton className="h-20 w-[212px] shrink-0 rounded-[10px]" />
        </div>
      )}
      <PaymentMethodPicker value={paymentMethod} onChange={onPaymentMethodChange} />
      <Button className="w-full" loading={ordering} disabled={!quote} onClick={onOrder}>
        {orderButtonLabel(tariff, paymentMethod)}
      </Button>
      {error && (
        <p role="alert" className="w-full text-center text-caption text-accent-danger">
          {error}
        </p>
      )}
      <p className="w-full text-center text-caption text-text-secondary lg:text-left">
        <span className="lg:hidden">{NOTE[paymentMethod]}</span>
        <span className="hidden lg:inline">
          {paymentMethod === 'kaspi_link' ? 'Деньги спишутся, когда найдётся водитель' : 'Наличные — водителю после поездки'} · точки можно
          выбрать кликом по карте
        </span>
      </p>
    </>
  )
}

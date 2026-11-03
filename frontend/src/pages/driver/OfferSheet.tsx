import { Banknote, Car, CircleDot, CreditCard, MapPin } from 'lucide-react'
import { errorMessage, type Coordinates } from '@/api'
import { formatRating, TARIFF_LABELS, type NextOffer } from '@/api/next-contract-driver'
import { Button, CountdownRing, ListRow, showToast, StatusPill } from '@/components/ui-kit'
import { useCountdown } from '@/hooks/use-countdown'
import { useAcceptOffer, useRejectOffer } from '@/hooks/use-driver'
import { useReverseGeocode } from '@/hooks/use-geocoding'
import { formatDistance, formatDuration, formatMoney } from '@/lib/format'
import { pickupLine } from './pickup-eta'

export const OFFER_TTL_S = 30

/** Figma Pay row (6:232). The offer has no payment method yet, so until it does the row shows the tariff. */
function PaymentLine({ offer }: { offer: NextOffer }) {
  const method = offer.payment_method
  const Icon = method === 'kaspi_link' ? CreditCard : method === 'cash' ? Banknote : Car
  const text =
    method === 'kaspi_link'
      ? 'Kaspi · оплачено при назначении'
      : method === 'cash'
        ? 'Оплата наличными'
        : `Тариф ${TARIFF_LABELS[offer.tariff ?? 'economy']}`
  return (
    <div className="flex w-full items-center gap-2">
      <Icon className="size-6 shrink-0 text-text-primary" strokeWidth={2} aria-hidden />
      <p className="text-callout text-text-secondary">{text}</p>
    </div>
  )
}

/** Figma 6:125: a 30-second offer; the ring follows the server `expires_at`. */
export function OfferSheet({
  offer,
  driverLocation,
  onAccepted,
}: {
  offer: NextOffer
  driverLocation: Coordinates | null
  onAccepted: (rideId: string) => void
}) {
  const secondsLeft = useCountdown(offer.expires_at)
  const accept = useAcceptOffer()
  const reject = useRejectOffer()
  const pickup = useReverseGeocode(offer.pickup)
  const dropoff = useReverseGeocode(offer.dropoff)
  const busy = accept.isPending || reject.isPending
  const expired = secondsLeft === 0
  const rating = formatRating(offer.passenger_rating)

  const fail = (error: Error) => showToast({ title: errorMessage(error) })

  return (
    <>
      <div className="flex w-full items-center gap-4">
        <div className="flex min-w-0 flex-1 flex-col items-start gap-1">
          <div className="flex items-center gap-1.5">
            <StatusPill tone="inverse">Новый заказ</StatusPill>
            {offer.payment_method && offer.tariff && offer.tariff !== 'economy' && (
              <StatusPill>{TARIFF_LABELS[offer.tariff]}</StatusPill>
            )}
          </div>
          <p className="text-display text-text-primary">{formatMoney(offer.amount_kzt)}</p>
          <p className="text-callout text-text-secondary">
            {pickupLine(driverLocation, offer.pickup)}
            {rating && ` · ${rating}`}
          </p>
        </div>
        <CountdownRing seconds={secondsLeft} total={OFFER_TTL_S} />
      </div>
      <div className="flex w-full flex-col">
        <ListRow icon={CircleDot} title={pickup.data?.title ?? 'Точка подачи'} subtitle="Подача" />
        <ListRow
          icon={MapPin}
          title={dropoff.data?.title ?? 'Точка назначения'}
          subtitle={`Назначение · ${formatDistance(offer.distance_m)} · ${formatDuration(offer.duration_s)}`}
        />
      </div>
      <PaymentLine offer={offer} />
      <div className="flex w-full items-center gap-3">
        <Button
          variant="secondary"
          className="flex-1"
          disabled={busy || expired}
          onClick={() => reject.mutate(offer.id, { onError: fail })}
        >
          Отклонить
        </Button>
        <Button
          className="flex-1"
          disabled={busy || expired}
          loading={accept.isPending}
          onClick={() => accept.mutate(offer.id, { onSuccess: (ride) => onAccepted(ride.id), onError: fail })}
        >
          Принять
        </Button>
      </div>
    </>
  )
}

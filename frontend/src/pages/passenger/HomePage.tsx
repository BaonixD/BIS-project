import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { ACTIVE_RIDE_STATUSES, isApiError, type Coordinates, type Quote } from '@/api'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { PointRow } from '@/components/common/PointRow'
import { BaseMap } from '@/components/map/BaseMap'
import { FitToPoints, PointMarker, RouteLine } from '@/components/map/layers'
import { MapScreen } from '@/components/map/MapScreen'
import { Button } from '@/components/ui/button'
import { useCountdown } from '@/hooks/use-countdown'
import { newIdempotencyKey, useActiveRide, useCreateRide, useQuote } from '@/hooks/use-rides'
import { formatDistance, formatDuration, formatMoney } from '@/lib/format'

type Target = 'pickup' | 'dropoff'

function QuoteSummary({ quote }: { quote: Quote }) {
  const secondsLeft = useCountdown(quote.expires_at)
  return (
    <div className="rounded-lg bg-muted p-3">
      <p className="text-2xl font-semibold">{formatMoney(quote.amount_kzt)}</p>
      <p className="text-sm text-muted-foreground">
        {formatDistance(quote.route.distance_m)} · {formatDuration(quote.route.duration_s)}
      </p>
      <p className="text-xs text-muted-foreground">
        {secondsLeft > 0 ? `Цена действует ещё ${Math.ceil(secondsLeft / 60)} мин` : 'Цена устарела'}
      </p>
    </div>
  )
}

export function HomePage() {
  const navigate = useNavigate()
  const activeRide = useActiveRide(ACTIVE_RIDE_STATUSES)
  const quote = useQuote()
  const createRide = useCreateRide()
  const [pickup, setPickup] = useState<Coordinates | null>(null)
  const [dropoff, setDropoff] = useState<Coordinates | null>(null)
  const [target, setTarget] = useState<Target>('pickup')

  if (activeRide.data) return <Navigate to={`/ride/${activeRide.data.id}`} replace />

  const pick = (point: Coordinates) => {
    quote.reset()
    createRide.reset()
    if (target === 'pickup') {
      setPickup(point)
      if (!dropoff) setTarget('dropoff')
    } else {
      setDropoff(point)
    }
  }

  const requestQuote = () => {
    if (pickup && dropoff) quote.mutate({ pickup, dropoff })
  }

  const order = (quoteId: string) =>
    createRide.mutate(
      { quoteId, idempotencyKey: newIdempotencyKey() },
      {
        onSuccess: (ride) => navigate(`/ride/${ride.id}`),
        onError: (error) => {
          if (isApiError(error, 'active_ride_exists')) void activeRide.refetch()
        },
      },
    )

  const points = [pickup, dropoff].filter((p): p is Coordinates => p !== null)

  return (
    <MapScreen
      map={
        <BaseMap onPick={pick}>
          {pickup && <PointMarker point={pickup} kind="pickup" />}
          {dropoff && <PointMarker point={dropoff} kind="dropoff" />}
          {quote.data && <RouteLine route={quote.data.route} />}
          <FitToPoints points={points} />
        </BaseMap>
      }
      sheet={
        <div className="grid gap-3">
          <h1 className="text-lg font-semibold">Куда поедем?</h1>
          <PointRow label="Откуда" point={pickup} color="#16a34a" active={target === 'pickup'} onSelect={() => setTarget('pickup')} />
          <PointRow label="Куда" point={dropoff} color="#dc2626" active={target === 'dropoff'} onSelect={() => setTarget('dropoff')} />
          {quote.data && <QuoteSummary quote={quote.data} />}
          <ErrorAlert error={quote.error ?? createRide.error} />
          {quote.data ? (
            <Button size="lg" disabled={createRide.isPending} onClick={() => quote.data && order(quote.data.quote_id)}>
              Заказать
            </Button>
          ) : (
            <Button size="lg" disabled={!pickup || !dropoff || quote.isPending} onClick={requestQuote}>
              Узнать цену
            </Button>
          )}
          {(quote.data || createRide.isError) && (
            <Button variant="ghost" onClick={requestQuote} disabled={quote.isPending}>
              Обновить цену
            </Button>
          )}
        </div>
      }
    />
  )
}

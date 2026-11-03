import { useNavigate, useParams } from 'react-router'
import { MapView } from '@/components/map/MapView'
import { FullScreen, ScreenHeader } from '@/components/passenger/layout'
import { RouteRows, SummaryRows } from '@/components/passenger/ride-parts'
import { driverLine } from '@/components/passenger/ride-text'
import { Button, Skeleton, StatusPill } from '@/components/ui-kit'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { usePassengerRide } from '@/hooks/use-rides'
import { formatClock, formatKm, formatMinutes, formatPrice, formatRideDate } from './model/format'
import { ridePill } from './model/history'
import { PAYMENT_LABELS, TARIFF_LABELS } from './model/order'
import { useRememberedDriver } from './ride/driver-cache'

/** 16px around the route in the 160px preview (FitToPoints adds 48px). */
const PREVIEW_INSETS = { top: -32, right: -32, bottom: -32, left: -32 }

/** Figma 24:708 «Детали поездки». */
export function RideDetailsPage() {
  const { rideId = '' } = useParams()
  const navigate = useNavigate()
  const query = usePassengerRide(rideId)
  const ride = query.data
  const driver = useRememberedDriver(rideId, ride?.driver)
  const pill = ride ? ridePill(ride) : null

  return (
    <FullScreen>
      <div className="mx-auto flex w-full max-w-[420px] flex-col gap-4 px-4 pt-[56px] pb-8 lg:pt-8">
        <ScreenHeader
          title="Поездка"
          subtitle={ride ? formatRideDate(ride.created_at) : undefined}
          trailing={pill && <StatusPill tone={pill.tone}>{pill.text}</StatusPill>}
          back={{ onClick: () => navigate(-1) }}
        />
        {query.isPending && <Skeleton className="h-40 w-full rounded-lg" />}
        <ErrorAlert error={query.error} />
        {ride && (
          <>
            <div className="h-40 w-full overflow-hidden rounded-lg bg-map-land [&_.leaflet-control-attribution]:text-[8px] [&_.leaflet-control-attribution]:leading-3">
              <MapView pickup={ride.pickup} dropoff={ride.dropoff} route={ride.route} center={ride.pickup} insets={PREVIEW_INSETS} />
            </div>
            <RouteRows
              pickup={ride.pickup}
              dropoff={ride.dropoff}
              pickupSubtitle={`${formatClock(ride.started_at ?? ride.created_at)} · посадка`}
              dropoffSubtitle={ride.completed_at ? `${formatClock(ride.completed_at)} · высадка` : 'Куда'}
            />
            <SummaryRows
              className="rounded-lg bg-bg-subtle p-4"
              rows={[
                ['Тариф', TARIFF_LABELS[ride.tariff]],
                ['Расстояние', `${formatKm(ride.route.distance_m)} · ${formatMinutes(ride.route.duration_s)}`],
                ...(driver ? ([['Водитель', driverLine(driver)]] as [string, string | null][]) : []),
                ['Оплата', `${ride.payment_method ? PAYMENT_LABELS[ride.payment_method] : '—'} · ${formatPrice(ride.amount_kzt)}`],
              ]}
            />
            {ride.status === 'completed' && !ride.my_rating && (
              <Button variant="secondary" className="w-full" onClick={() => navigate(`/ride/${ride.id}`)}>
                Оценить поездку
              </Button>
            )}
          </>
        )}
      </div>
    </FullScreen>
  )
}

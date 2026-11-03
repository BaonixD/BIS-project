import { useEffect, useState } from 'react'
import { Navigation, Timer } from 'lucide-react'
import {
  DRIVER_ACTIVE_RIDE_STATUSES,
  errorMessage,
  isApiError,
  type Coordinates,
  type RideSummary,
} from '@/api'
import type { NextRide } from '@/api/driver-types'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { FullScreenLoader } from '@/components/common/FullScreenLoader'
import { DashedLine } from '@/components/driver/DashedLine'
import { MapBanner, OnlinePill } from '@/components/driver/MapBanner'
import { Screen, ScreenColumn } from '@/components/driver/Screen'
import { FitToPoints, type MapInsets } from '@/components/map/layers'
import { MapView, type MapViewProps } from '@/components/map/MapView'
import { useMapInsets } from '@/components/map/use-map-insets'
import { BottomSheet, showToast } from '@/components/ui-kit'
import { useNow } from '@/hooks/use-countdown'
import {
  useDriverOffers,
  useDriverProfile,
  useOnlineSince,
  useSetAvailability,
  useTrackedRideId,
} from '@/hooks/use-driver'
import { useReverseGeocode } from '@/hooks/use-geocoding'
import { useLocationReporter } from '@/hooks/use-location-reporter'
import { usePayment } from '@/hooks/use-payment'
import { useActiveRide, useRide, useRideHistory } from '@/hooks/use-rides'
import { formatDistance } from '@/lib/format'
import { selectDriverScreen, type DriverScreen } from './driver-screen'
import { DriverMapLayout, GoOnlineButton, SearchingPulse } from './DriverMapLayout'
import { OfferSheet } from './OfferSheet'
import { formatWait, haversineM } from './pickup-eta'
import { CollectCashScreen, CompletedScreen } from './RideResultScreens'
import { CancelledSheet, ReleaseSheet, RideSheet } from './RideSheets'
import { periodStart, summarizeShift } from './shift-stats'
import { OfflineSheet, OnlineSheet, PendingSheet } from './ShiftSheets'

const BANNER_INSET = 90
const EMPTY: RideSummary[] = []

function useTodayStats() {
  const [createdFrom] = useState(() => periodStart('today', new Date()))
  const history = useRideHistory({ status: ['completed'], created_from: createdFrom, limit: 100 })
  return summarizeShift(history.data?.items ?? EMPTY)
}

/** Ride id the driver is tracking, the ride itself and its payment; a 404 (after release) forgets it. */
function useDriverRide() {
  const active = useActiveRide(DRIVER_ACTIVE_RIDE_STATUSES)
  const [rideId, track] = useTrackedRideId(active.data?.id)
  const ride = useRide(rideId ?? undefined)
  const lost = isApiError(ride.error) && ride.error.status === 404

  useEffect(() => {
    if (lost) track(null)
  }, [lost, track])

  const data = (rideId && !lost ? ride.data : undefined) as NextRide | undefined
  const cashDue = data?.status === 'completed' && data.payment_method === 'cash'
  const payment = usePayment(data?.id ?? '', { enabled: Boolean(cashDue) })
  return { ride: data ?? null, rideId, track, paymentStatus: payment.data?.status ?? null }
}

function mapFor(screen: DriverScreen, me: Coordinates | null, insets: MapInsets): Partial<MapViewProps> {
  switch (screen.kind) {
    case 'offer':
      return {
        me,
        pickup: screen.offer.pickup,
        fit: false,
        children: (
          <>
            {me && <DashedLine from={me} to={screen.offer.pickup} />}
            <FitToPoints points={me ? [me, screen.offer.pickup] : [screen.offer.pickup]} insets={insets} />
          </>
        ),
      }
    case 'ride': {
      const { ride } = screen
      if (ride.status === 'arrived') return { pickup: ride.pickup, driver: me }
      if (ride.status === 'in_progress') return { route: ride.route, dropoff: ride.dropoff, driver: me }
      return { route: ride.route, pickup: ride.pickup, dropoff: ride.dropoff, driver: me }
    }
    default:
      return {}
  }
}

function RideBanner({ ride, me }: { ride: NextRide; me: Coordinates | null }) {
  const pickup = useReverseGeocode(ride.pickup)
  const dropoff = useReverseGeocode(ride.status === 'in_progress' ? ride.dropoff : null)
  const now = useNow(1000, ride.status === 'arrived')
  const pickupTitle = pickup.data?.title ?? 'Точка подачи'

  if (ride.status === 'arrived') {
    return (
      <MapBanner
        icon={Timer}
        title={`Вы на месте · ожидание ${formatWait(ride.arrived_at, now)}`}
        subtitle={`${pickupTitle} — пассажир получил уведомление`}
      />
    )
  }
  if (ride.status === 'in_progress') {
    const minutes = Math.max(1, Math.round(ride.route.duration_s / 60))
    return (
      <MapBanner
        icon={Navigation}
        title={`Едьте в ${dropoff.data?.title ?? 'точку назначения'}`}
        subtitle={`${formatDistance(ride.route.distance_m)} · около ${minutes} мин`}
      />
    )
  }
  const distance = me ? ` · ${formatDistance(haversineM(me, ride.pickup))}` : ''
  return <MapBanner icon={Navigation} title="Едьте к пассажиру" subtitle={`${pickupTitle}${distance}`} />
}

export function DriverHomePage() {
  const driverQuery = useDriverProfile()
  const availability = useSetAvailability()
  const { ride, rideId, track, paymentStatus } = useDriverRide()
  const [manualPoint, setManualPoint] = useState<Coordinates | null>(null)
  const [releasing, setReleasing] = useState(false)
  const [sheetHeight, setSheetHeight] = useState(0)
  const insets = useMapInsets(sheetHeight)

  const driver = driverQuery.data
  const online = driver?.online ?? false
  const reporter = useLocationReporter(online, manualPoint)
  const offers = useDriverOffers({ enabled: online && !rideId })
  const stats = useTodayStats()
  const onlineSince = useOnlineSince(online)
  const now = useNow(30_000, online)

  if (driverQuery.isPending) return <FullScreenLoader />
  if (!driver) {
    return (
      <Screen>
        <ScreenColumn className="pt-6">
          <ErrorAlert error={driverQuery.error} />
        </ScreenColumn>
      </Screen>
    )
  }

  const offer = offers.data?.items.find((item) => item.status === 'pending') ?? null
  const screen = selectDriverScreen({ driver, ride, offer, paymentStatus })
  const me = reporter.position ?? driver.location
  const dismiss = () => {
    setReleasing(false)
    track(null)
  }

  if (screen.kind === 'collect-cash') return <CollectCashScreen ride={screen.ride} />
  if (screen.kind === 'completed') return <CompletedScreen ride={screen.ride} paidBy={screen.paidBy} onDone={dismiss} />

  const setOnline = (value: boolean) =>
    availability.mutate(value, { onError: (error) => showToast({ title: errorMessage(error) }) })
  const immersive = ['offer', 'ride', 'cancelled'].includes(screen.kind)
  const withBanner = screen.kind === 'ride' && !releasing

  const top =
    screen.kind === 'pending' ? (
      <MapBanner
        tone="warning"
        icon={Timer}
        title="Аккаунт на проверке"
        subtitle="Выйти на линию можно после одобрения"
      />
    ) : screen.kind === 'offline' || screen.kind === 'online' ? (
      <OnlinePill online={screen.kind === 'online'} />
    ) : withBanner ? (
      <RideBanner ride={screen.ride} me={me} />
    ) : null

  return (
    <DriverMapLayout
      immersive={immersive}
      top={top}
      map={
        <MapView
          center={me ?? undefined}
          insets={withBanner ? { ...insets, top: BANNER_INSET } : insets}
          onPick={online && reporter.needsManualPoint ? setManualPoint : undefined}
          {...mapFor(screen, me, insets)}
        />
      }
    >
      {screen.kind === 'offline' && (
        <GoOnlineButton sheetHeight={sheetHeight} loading={availability.isPending} onClick={() => setOnline(true)} />
      )}
      {screen.kind === 'pending' && <GoOnlineButton sheetHeight={sheetHeight} disabled onClick={() => undefined} />}
      {screen.kind === 'online' && <SearchingPulse sheetHeight={sheetHeight} />}

      {screen.kind === 'cancelled' ? (
        <CancelledSheet online={online} onDismiss={dismiss} />
      ) : screen.kind === 'ride' && releasing ? (
        <ReleaseSheet ride={screen.ride} onClose={() => setReleasing(false)} onReleased={dismiss} />
      ) : (
        <BottomSheet
          aria-label="Смена"
          onHeightChange={setSheetHeight}
          className={screen.kind === 'ride' && screen.ride.status !== 'assigned' ? 'pb-7' : undefined}
        >
          {screen.kind === 'pending' && <PendingSheet driver={driver} />}
          {screen.kind === 'offline' && <OfflineSheet stats={stats} />}
          {screen.kind === 'online' && (
            <OnlineSheet
              stats={stats}
              onlineS={onlineSince ? (now - onlineSince) / 1000 : 0}
              manualHint={reporter.needsManualPoint && !reporter.position}
              leaving={availability.isPending}
              onLeave={() => setOnline(false)}
            />
          )}
          {screen.kind === 'offer' && (
            <OfferSheet key={screen.offer.id} offer={screen.offer} driverLocation={me} onAccepted={track} />
          )}
          {screen.kind === 'ride' && <RideSheet ride={screen.ride} onRelease={() => setReleasing(true)} />}
        </BottomSheet>
      )}
    </DriverMapLayout>
  )
}

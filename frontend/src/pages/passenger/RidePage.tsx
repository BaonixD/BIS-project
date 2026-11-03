import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import type { LatLngTuple } from 'leaflet'
import { Polyline } from 'react-leaflet'
import { Car } from 'lucide-react'
import type { RideDetails, RideStatus } from '@/api'
import { FullScreenLoader } from '@/components/common/FullScreenLoader'
import { FitToPoints, type MapInsets } from '@/components/map/layers'
import { MapView } from '@/components/map/MapView'
import { useMapInsets } from '@/components/map/use-map-insets'
import { FullScreen, MapLayout } from '@/components/passenger/layout'
import { PulseMarker } from '@/components/passenger/map-layers'
import { StatusHeading } from '@/components/passenger/ride-parts'
import { Button, Skeleton, showToast } from '@/components/ui-kit'
import { useNow } from '@/hooks/use-countdown'
import { useCancelRide, usePassengerRide } from '@/hooks/use-rides'
import { routeToLatLngs, toLatLng } from '@/lib/geo'
import type { ReorderState } from './home/flow'
import { passengerErrorMessage } from './model/errors'
import { driverFoundSeen, isPaidKaspi, markDriverFoundSeen, rideScreen, wasReleased, type RideScreen } from './model/ride-screen'
import { useRememberedDriver } from './ride/driver-cache'
import { CancelledScreen, CompletedScreen, PayCashScreen } from './ride/FinishScreens'
import {
  ArrivedSheet,
  CancelConfirmSheet,
  DriverFoundSheet,
  InProgressSheet,
  NoDriverSheet,
  OnTheWaySheet,
  SearchingSheet,
} from './ride/TrackingSheets'

/** Remembers the last status to notice a release (assigned → searching) and when it happened. */
function useDeclinedAt(ride: RideDetails | undefined, now: number): number | null {
  const [tracked, setTracked] = useState<{ status?: RideStatus; declinedAt: number | null }>({ declinedAt: null })
  if (ride && ride.status !== tracked.status) {
    const released = wasReleased(tracked.status, ride.status)
    const keep = ride.status === 'searching' ? tracked.declinedAt : null
    setTracked({ status: ride.status, declinedAt: released ? now : keep })
  }
  const { declinedAt } = tracked
  const paid = ride ? isPaidKaspi(ride) : false

  useEffect(() => {
    if (declinedAt === null) return
    showToast({
      title: 'Водитель отказался от заказа',
      description: paid ? 'Уже ищем другого — оплата сохранится за новым водителем' : 'Уже ищем другого водителя',
      icon: Car,
      duration: 6000,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- one toast per release
  }, [declinedAt])

  return declinedAt
}

function RideMap({ ride, screen, insets, ready }: { ride: RideDetails; screen: RideScreen; insets: MapInsets; ready: boolean }) {
  const driver = ride.driver?.location ?? null
  if (screen === 'searching' || screen === 'no_driver') {
    return (
      <MapView center={ride.pickup} fit={false}>
        {screen === 'searching' && <PulseMarker point={ride.pickup} />}
        {ready && <FitToPoints points={[ride.pickup]} insets={insets} />}
      </MapView>
    )
  }
  if (screen === 'in_progress') {
    const ahead = [...(driver ? [toLatLng(driver)] : []), ...routeToLatLngs(ride.route), toLatLng(ride.dropoff)]
    return (
      <MapView center={ride.pickup} dropoff={ride.dropoff} route={ride.route} driver={driver} fit={false}>
        {ready && <FitToPoints points={ahead} insets={insets} />}
      </MapView>
    )
  }
  const approach: LatLngTuple[] | null = screen === 'on_the_way' && driver ? [toLatLng(driver), toLatLng(ride.pickup)] : null
  return (
    <MapView center={ride.pickup} pickup={ride.pickup} driver={driver} fit={false}>
      {approach && <Polyline positions={approach} pathOptions={APPROACH_LINE} />}
      {ready && <FitToPoints points={driver ? [driver, ride.pickup] : [ride.pickup]} insets={insets} />}
    </MapView>
  )
}

/** Figma 5:434 «DriverApproach»: a dotted line from the car to the pickup. */
const APPROACH_LINE = { color: '#000000', weight: 4, opacity: 1, dashArray: '0.1 8', lineCap: 'round' as const }

function reorderState(ride: RideDetails, step: ReorderState['step']): ReorderState {
  return {
    pickup: ride.pickup,
    dropoff: ride.dropoff,
    tariff: ride.tariff,
    paymentMethod: ride.payment_method ?? undefined,
    step,
  }
}

/** A passenger ride: the screen follows the status of the polled `GET /rides/{id}`. */
export function RidePage() {
  const { rideId = '' } = useParams()
  const navigate = useNavigate()
  const query = usePassengerRide(rideId)
  const cancel = useCancelRide(rideId)
  const now = useNow(1000)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [foundSeen, setFoundSeen] = useState(() => driverFoundSeen(rideId))
  const [sheetHeight, setSheetHeight] = useState(0)
  const insets = useMapInsets(sheetHeight)
  const ride = query.data
  const declinedAt = useDeclinedAt(ride, now)
  const driver = useRememberedDriver(rideId, ride?.driver)

  if (query.isPending) return <FullScreenLoader />
  if (!ride) {
    return (
      <FullScreen>
        <div className="mx-auto flex min-h-full max-w-[420px] flex-col items-center justify-center gap-6 px-4">
          <StatusHeading icon={Car} title="Поездка недоступна" text={passengerErrorMessage(query.error)} />
          <Button className="w-full" onClick={() => navigate('/', { replace: true })}>
            На главную
          </Button>
        </div>
      </FullScreen>
    )
  }

  const screen = rideScreen(ride, { driverFoundSeen: foundSeen })
  const goHome = (message?: string) => {
    if (message) showToast({ title: message })
    navigate('/', { replace: true })
  }
  const reorder = (step: ReorderState['step']) => navigate('/', { replace: true, state: reorderState(ride, step) })

  if (screen === 'pay_cash') return <PayCashScreen ride={ride} driver={driver} onDone={() => goHome()} />
  if (screen === 'completed') return <CompletedScreen ride={ride} driver={driver} onDone={goHome} />
  if (screen === 'cancelled') return <CancelledScreen ride={ride} onReorder={() => reorder('choose')} />

  const openCancel = () => {
    cancel.reset()
    setConfirmCancel(true)
  }
  const cancellable = ['searching', 'assigned', 'arrived'].includes(ride.status)
  const showConfirm = confirmCancel && cancellable

  let sheet
  let sheetClassName = 'pb-7'
  let centered = false
  let dimmed = false
  if (showConfirm) {
    centered = true
    dimmed = true
    sheetClassName = 'gap-[18px] pb-7'
    sheet = (
      <CancelConfirmSheet
        ride={ride}
        pending={cancel.isPending}
        error={cancel.error ? passengerErrorMessage(cancel.error) : null}
        onConfirm={() => cancel.mutate(undefined, { onSuccess: () => setConfirmCancel(false) })}
        onClose={() => setConfirmCancel(false)}
      />
    )
  } else if (screen === 'searching') {
    sheetClassName = declinedAt ? 'pb-7' : 'pb-5'
    sheet = <SearchingSheet ride={ride} now={now} declinedAt={declinedAt} onCancel={openCancel} />
  } else if (screen === 'driver_found' && driver) {
    centered = true
    dimmed = true
    sheetClassName = 'gap-[18px] pb-7'
    const track = () => {
      markDriverFoundSeen(rideId)
      setFoundSeen(true)
    }
    sheet = <DriverFoundSheet ride={ride} driver={driver} onTrack={track} onReceipt={() => navigate(`/history/${ride.id}`)} />
  } else if ((screen === 'on_the_way' || screen === 'driver_found') && driver) {
    sheetClassName = 'pb-5'
    sheet = <OnTheWaySheet ride={ride} driver={driver} onCancel={openCancel} />
  } else if (screen === 'arrived' && driver) {
    sheet = <ArrivedSheet ride={ride} driver={driver} now={now} onCancel={openCancel} />
  } else if (screen === 'in_progress') {
    sheet = <InProgressSheet ride={ride} driver={driver} now={now} />
  } else if (screen === 'no_driver') {
    centered = true
    sheetClassName = 'gap-[18px] pb-7'
    sheet = <NoDriverSheet ride={ride} onRetry={() => reorder('choose')} onEditRoute={() => reorder('search')} />
  } else {
    sheet = <Skeleton className="h-40 w-full rounded-lg" />
  }

  return (
    <MapLayout
      map={<RideMap ride={ride} screen={screen} insets={insets} ready={sheetHeight > 0} />}
      sheet={sheet}
      sheetLabel="Поездка"
      sheetClassName={sheetClassName}
      centered={centered}
      dimmed={dimmed}
      onSheetHeightChange={setSheetHeight}
    />
  )
}

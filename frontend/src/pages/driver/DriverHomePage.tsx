import { useState } from 'react'
import { Link } from 'react-router'
import { LocateFixed, MapPinned } from 'lucide-react'
import { DRIVER_ACTIVE_RIDE_STATUSES, isRideActive, type Coordinates, type Driver } from '@/api'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { FullScreenLoader } from '@/components/common/FullScreenLoader'
import { PageContainer } from '@/components/layout/PageContainer'
import { BaseMap } from '@/components/map/BaseMap'
import { FitToPoints, PointMarker, RouteLine } from '@/components/map/layers'
import { MapScreen } from '@/components/map/MapScreen'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useDriverOffers, useDriverProfile, useSetAvailability } from '@/hooks/use-driver'
import { useLocationReporter, type LocationReporter } from '@/hooks/use-location-reporter'
import { useActiveRide, useRide } from '@/hooks/use-rides'
import { formatDateTime } from '@/lib/format'
import { ActiveRidePanel } from './ActiveRidePanel'
import { OfferCard } from './OfferCard'

function LocationStatus({ reporter }: { reporter: LocationReporter }) {
  if (reporter.needsManualPoint && !reporter.position) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <MapPinned className="size-4" aria-hidden /> Геолокация недоступна — нажмите на карту, где вы находитесь
      </p>
    )
  }
  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <LocateFixed className="size-4" aria-hidden />
      {reporter.source === 'manual' ? 'Точка выбрана вручную' : 'GPS'}
      {reporter.lastSentAt && ` · отправлено ${formatDateTime(reporter.lastSentAt)}`}
    </p>
  )
}

function NotApproved({ driver }: { driver: Driver }) {
  return (
    <Alert>
      <AlertTitle>Ожидает допуска администратора</AlertTitle>
      <AlertDescription>
        {driver.missing_fields.length > 0 ? 'Заполните профиль и машину, затем дождитесь допуска.' : 'Профиль заполнен, дождитесь допуска.'}
        <Button asChild variant="link" className="h-auto p-0">
          <Link to="/driver/profile">Открыть профиль</Link>
        </Button>
      </AlertDescription>
    </Alert>
  )
}

export function DriverHomePage() {
  const driver = useDriverProfile()
  const availability = useSetAvailability()
  const activeRideSummary = useActiveRide(DRIVER_ACTIVE_RIDE_STATUSES)
  const activeRide = useRide(activeRideSummary.data?.id)
  const [manualPoint, setManualPoint] = useState<Coordinates | null>(null)

  const online = driver.data?.online ?? false
  const reporter = useLocationReporter(online, manualPoint)
  const hasActiveRide = Boolean(activeRide.data && isRideActive(activeRide.data.status))
  const offers = useDriverOffers({ enabled: online && !activeRideSummary.data })
  const offer = offers.data?.items.find((item) => item.status === 'pending')

  if (driver.isPending) return <FullScreenLoader />
  if (driver.isError) {
    return (
      <PageContainer>
        <ErrorAlert error={driver.error} />
      </PageContainer>
    )
  }

  const approved = driver.data.approval_status === 'approved'
  const shownRide = activeRide.data ?? null
  const mapPoints = [reporter.position, shownRide?.pickup, shownRide?.dropoff, offer?.pickup].filter(
    (point): point is Coordinates => Boolean(point),
  )

  return (
    <MapScreen
      map={
        <BaseMap onPick={reporter.needsManualPoint && online ? setManualPoint : undefined}>
          {reporter.position && <PointMarker point={reporter.position} kind="driver" />}
          {shownRide && <PointMarker point={shownRide.pickup} kind="pickup" />}
          {shownRide && <PointMarker point={shownRide.dropoff} kind="dropoff" />}
          {shownRide && <RouteLine route={shownRide.route} />}
          {!shownRide && offer && <PointMarker point={offer.pickup} kind="pickup" />}
          {!shownRide && offer && <PointMarker point={offer.dropoff} kind="dropoff" />}
          <FitToPoints points={mapPoints} />
        </BaseMap>
      }
      sheet={
        <div className="grid gap-3">
          {!approved && <NotApproved driver={driver.data} />}
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="online" className="text-base font-semibold">
              {online ? 'На линии' : 'Не на линии'}
            </Label>
            <Switch
              id="online"
              checked={online}
              disabled={!approved || availability.isPending}
              onCheckedChange={(checked) => availability.mutate(checked)}
            />
          </div>
          <ErrorAlert error={availability.error ?? reporter.sendError} />
          {online && <LocationStatus reporter={reporter} />}
          {shownRide && (hasActiveRide || shownRide.status === 'cancelled') && <ActiveRidePanel ride={shownRide} onDismiss={() => void activeRideSummary.refetch()} />}
          {!shownRide && offer && <OfferCard key={offer.id} offer={offer} />}
          {online && !shownRide && !offer && (
            <p className="text-sm text-muted-foreground">Ждём заказы поблизости…</p>
          )}
        </div>
      }
    />
  )
}

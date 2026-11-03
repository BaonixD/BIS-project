import { Link, useParams } from 'react-router'
import { LoaderCircle } from 'lucide-react'
import type { RideStatus } from '@/api'
import { DriverInfo } from '@/components/common/DriverInfo'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { FullScreenLoader } from '@/components/common/FullScreenLoader'
import { RideStatusBadge } from '@/components/common/RideStatusBadge'
import { MapScreen } from '@/components/map/MapScreen'
import { RideMap } from '@/components/map/RideMap'
import { Button } from '@/components/ui/button'
import { PageContainer } from '@/components/layout/PageContainer'
import { useNow } from '@/hooks/use-countdown'
import { useCancelRide, useRide } from '@/hooks/use-rides'
import { formatDistance, formatDuration, formatMoney } from '@/lib/format'
import { PaymentPanel } from './PaymentPanel'

const CANCELLABLE: RideStatus[] = ['searching', 'assigned', 'arrived']

export function RidePage() {
  const { rideId = '' } = useParams()
  const ride = useRide(rideId)
  const cancel = useCancelRide(rideId)
  const now = useNow(30_000)

  if (ride.isPending) return <FullScreenLoader />
  if (ride.isError) {
    return (
      <PageContainer>
        <ErrorAlert error={ride.error} />
        <Button asChild variant="outline" className="mt-4">
          <Link to="/">На главную</Link>
        </Button>
      </PageContainer>
    )
  }

  const data = ride.data
  return (
    <MapScreen
      map={
        <RideMap
          pickup={data.pickup}
          dropoff={data.dropoff}
          route={data.route}
          driverLocation={data.driver?.location}
        />
      }
      sheet={
        <div className="grid gap-3">
          <div className="flex items-center justify-between gap-2">
            <RideStatusBadge status={data.status} />
            <span className="text-lg font-semibold">{formatMoney(data.amount_kzt)}</span>
          </div>
          <p className="text-sm text-muted-foreground">
            {formatDistance(data.route.distance_m)} · {formatDuration(data.route.duration_s)}
          </p>
          {data.status === 'searching' && (
            <p className="flex items-center gap-2 text-sm">
              <LoaderCircle className="size-4 animate-spin" aria-hidden /> Ищем ближайшего водителя…
            </p>
          )}
          {data.driver && <DriverInfo driver={data.driver} now={now} />}
          {data.status === 'completed' && <PaymentPanel rideId={data.id} />}
          {data.status === 'no_driver' && (
            <Button asChild size="lg">
              <Link to="/">Заказать снова</Link>
            </Button>
          )}
          {data.status === 'cancelled' && (
            <Button asChild variant="outline">
              <Link to="/">Новый заказ</Link>
            </Button>
          )}
          <ErrorAlert error={cancel.error} />
          {CANCELLABLE.includes(data.status) && (
            <Button variant="outline" disabled={cancel.isPending} onClick={() => cancel.mutate(undefined)}>
              Отменить поездку
            </Button>
          )}
        </div>
      }
    />
  )
}

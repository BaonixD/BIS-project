import type { Coordinates, RouteResult } from '@/api'
import { BaseMap } from './BaseMap'
import { FitToPoints, PointMarker, RouteLine } from './layers'

interface RideMapProps {
  pickup: Coordinates
  dropoff: Coordinates
  route?: RouteResult
  driverLocation?: Coordinates | null
  className?: string
}

export function RideMap({ pickup, dropoff, route, driverLocation, className }: RideMapProps) {
  return (
    <BaseMap className={className} center={pickup}>
      <PointMarker point={pickup} kind="pickup" />
      <PointMarker point={dropoff} kind="dropoff" />
      {route && <RouteLine route={route} />}
      {driverLocation && <PointMarker point={driverLocation} kind="driver" />}
      <FitToPoints points={[pickup, dropoff]} />
    </BaseMap>
  )
}

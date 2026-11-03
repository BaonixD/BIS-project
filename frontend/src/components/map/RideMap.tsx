import type { Coordinates, RouteResult } from '@/api'
import type { MapInsets } from './layers'
import { MapView } from './MapView'

interface RideMapProps {
  pickup: Coordinates
  dropoff: Coordinates
  route?: RouteResult
  driverLocation?: Coordinates | null
  insets?: MapInsets
  className?: string
}

export function RideMap({ pickup, dropoff, route, driverLocation, insets, className }: RideMapProps) {
  return (
    <MapView
      className={className}
      center={pickup}
      pickup={pickup}
      dropoff={dropoff}
      route={route}
      driver={driverLocation}
      insets={insets}
    />
  )
}

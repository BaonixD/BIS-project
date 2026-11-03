import type { ReactNode } from 'react'
import type { LatLngTuple } from 'leaflet'
import type { Coordinates, RouteResult } from '@/api'
import { routeToLatLngs, toLatLng } from '@/lib/geo'
import { BaseMap } from './BaseMap'
import { FitToPoints, PointMarker, RouteLine, type MapInsets } from './layers'

export interface MapViewProps {
  className?: string
  center?: Coordinates
  zoom?: number
  pickup?: Coordinates | null
  dropoff?: Coordinates | null
  driver?: Coordinates | null
  me?: Coordinates | null
  route?: RouteResult | LatLngTuple[] | null
  /** Map click → coordinates (choosing a point on the map). */
  onPick?: (point: Coordinates) => void
  /** Pixels hidden by overlays; see `useMapInsets`. */
  insets?: MapInsets
  /** Fit to the pickup/drop-off/route/driver whenever they change (default on). */
  fit?: boolean
  children?: ReactNode
}

function fitPoints({ route, pickup, dropoff, driver }: Pick<MapViewProps, 'route' | 'pickup' | 'dropoff' | 'driver'>) {
  const points: LatLngTuple[] = route ? (Array.isArray(route) ? [...route] : routeToLatLngs(route)) : []
  for (const point of [pickup, dropoff, driver]) if (point) points.push(toLatLng(point))
  return points
}

/**
 * The app map: CARTO Positron tiles centred on Almaty with Figma markers —
 * pickup ●, drop-off ■, driver car, «me» blue dot — and a black route line.
 */
export function MapView({
  className,
  center,
  zoom,
  pickup,
  dropoff,
  driver,
  me,
  route,
  onPick,
  insets,
  fit = true,
  children,
}: MapViewProps) {
  return (
    <BaseMap className={className} center={center} zoom={zoom} onPick={onPick}>
      {route && <RouteLine route={route} />}
      {me && <PointMarker point={me} kind="me" />}
      {pickup && <PointMarker point={pickup} kind="pickup" />}
      {dropoff && <PointMarker point={dropoff} kind="dropoff" />}
      {driver && <PointMarker point={driver} kind="driver" />}
      {fit && <FitToPoints points={fitPoints({ route, pickup, dropoff, driver })} insets={insets} />}
      {children}
    </BaseMap>
  )
}

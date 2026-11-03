import { useEffect } from 'react'
import { Marker, Polyline, useMap } from 'react-leaflet'
import { latLngBounds, type LatLngTuple } from 'leaflet'
import type { Coordinates, RouteResult } from '@/api'
import { routeToLatLngs, toLatLng } from '@/lib/geo'
import { carIcon, dropoffIcon, myLocationIcon, pickupIcon } from './markers'

export type PointKind = 'pickup' | 'dropoff' | 'driver' | 'me'

const MARKERS = {
  pickup: { icon: pickupIcon, label: 'Откуда' },
  dropoff: { icon: dropoffIcon, label: 'Куда' },
  driver: { icon: carIcon, label: 'Водитель' },
  me: { icon: myLocationIcon, label: 'Вы здесь' },
} as const

const ROUTE_ATTRIBUTION =
  'Маршрут &copy; <a href="https://openrouteservice.org/">openrouteservice.org</a> by HeiGIT'

export function PointMarker({ point, kind }: { point: Coordinates; kind: PointKind }) {
  const { icon, label } = MARKERS[kind]
  return (
    <Marker
      position={toLatLng(point)}
      icon={icon}
      title={label}
      alt={label}
      keyboard={false}
      interactive={false}
      zIndexOffset={kind === 'driver' ? 1000 : 0}
    />
  )
}

/** Route lines use the brand green (accent/success). */
export const ROUTE_COLOR = '#05A357'

/** Figma route line: green, 5px, round caps. */
export function RouteLine({ route }: { route: RouteResult | LatLngTuple[] }) {
  const positions = Array.isArray(route) ? route : routeToLatLngs(route)
  return (
    <Polyline
      positions={positions}
      pathOptions={{ color: ROUTE_COLOR, weight: 5, opacity: 1, lineCap: 'round', lineJoin: 'round' }}
      attribution={Array.isArray(route) ? undefined : ROUTE_ATTRIBUTION}
    />
  )
}

export interface MapInsets {
  top?: number
  right?: number
  bottom?: number
  left?: number
}

const FIT_PADDING = 48

/** Fits the view to the points, keeping them clear of overlays (bottom sheet, desktop panel). */
export function FitToPoints({ points: input, insets = {} }: { points: (Coordinates | LatLngTuple)[]; insets?: MapInsets }) {
  const map = useMap()
  const { top = 0, right = 0, bottom = 0, left = 0 } = insets
  const points = input.map((point) => (Array.isArray(point) ? point : toLatLng(point)))
  const key = points.map(([lat, lng]) => `${lat.toFixed(5)},${lng.toFixed(5)}`).join('|')

  useEffect(() => {
    if (points.length === 0) return
    map.fitBounds(latLngBounds(points), {
      paddingTopLeft: [left + FIT_PADDING, top + FIT_PADDING],
      paddingBottomRight: [right + FIT_PADDING, bottom + FIT_PADDING],
      maxZoom: 16,
      animate: true,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` captures the points
  }, [map, key, top, right, bottom, left])

  return null
}

import { t, useLocale } from '@/i18n/core'
import { useEffect, type ReactNode } from 'react'
import { Marker, Polyline, Tooltip, useMap } from 'react-leaflet'
import {
  latLngBounds,
  type LatLngTuple,
  type LeafletEvent,
  type Polyline as LeafletPolyline,
} from 'leaflet'
import type { Coordinates, RouteResult } from '@/api'
import { routeToLatLngs, toLatLng } from '@/lib/geo'
import { routeAttribution } from './attribution'
import { carIcon, dropoffIcon, myLocationIcon, pickupIcon } from './markers'
export type PointKind = 'pickup' | 'dropoff' | 'driver' | 'me'
const MARKERS = () =>
  ({
    pickup: { icon: pickupIcon, label: t('Откуда') },
    dropoff: { icon: dropoffIcon, label: t('Куда') },
    driver: { icon: carIcon, label: t('Водитель') },
    me: { icon: myLocationIcon, label: t('Вы здесь') },
  }) as const
export function PointMarker({
  point,
  kind,
  children,
}: {
  point: Coordinates
  kind: PointKind
  children?: ReactNode
}) {
  useLocale()
  const { icon, label } = MARKERS()[kind]
  return (
    <Marker
      position={toLatLng(point)}
      icon={icon}
      title={label}
      alt={label}
      keyboard={false}
      interactive={false}
      zIndexOffset={kind === 'driver' ? 1000 : 0}
    >
      {children && (
        <Tooltip
          permanent
          direction="top"
          offset={[0, -18]}
          className="bis-arrival-label"
          opacity={1}
        >
          {children}
        </Tooltip>
      )}
    </Marker>
  )
}
/** Route lines use the brand green (accent/success). */
/** Deep sky blue of the TezJet palette; strong enough over the light basemap. */
export const ROUTE_COLOR = '#0096AE'
const ROUTE_EVENTS = {
  add({ target }: LeafletEvent) {
    // Normalized length keeps the reveal consistent while the map zooms or pans.
    const path = (target as LeafletPolyline).getElement()
    path?.setAttribute('pathLength', '1')
  },
}
/** Reveal a new route once; polling the same geometry keeps the existing line. */
export function RouteLine({ route }: { route: RouteResult | LatLngTuple[] }) {
  useLocale()
  const positions = Array.isArray(route) ? route : routeToLatLngs(route)
  const attribution = Array.isArray(route) ? undefined : routeAttribution(route.provider)
  const geometryKey = positions.map(([lat, lng]) => `${lat},${lng}`).join(';')
  return (
    <Polyline
      key={`${attribution ?? 'no-attribution'}:${geometryKey}`}
      positions={positions}
      className="bis-route-line"
      noClip
      interactive={false}
      eventHandlers={ROUTE_EVENTS}
      pathOptions={{
        color: ROUTE_COLOR,
        weight: 5,
        opacity: 1,
        lineCap: 'round',
        lineJoin: 'round',
      }}
      attribution={attribution}
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
export function FitToPoints({
  points: input,
  insets = {},
}: {
  points: (Coordinates | LatLngTuple)[]
  insets?: MapInsets
}) {
  useLocale()
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

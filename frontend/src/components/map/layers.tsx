import { useEffect } from 'react'
import { CircleMarker, Polyline, Tooltip, useMap } from 'react-leaflet'
import { latLngBounds } from 'leaflet'
import type { Coordinates, RouteResult } from '@/api'
import { routeToLatLngs, toLatLng } from '@/lib/geo'

export type PointKind = 'pickup' | 'dropoff' | 'driver'

const POINT_STYLE: Record<PointKind, { color: string; label: string }> = {
  pickup: { color: '#16a34a', label: 'Откуда' },
  dropoff: { color: '#dc2626', label: 'Куда' },
  driver: { color: '#2563eb', label: 'Водитель' },
}

const ROUTE_ATTRIBUTION =
  'Маршрут &copy; <a href="https://openrouteservice.org/">openrouteservice.org</a> by HeiGIT'

export function PointMarker({ point, kind }: { point: Coordinates; kind: PointKind }) {
  const { color, label } = POINT_STYLE[kind]
  return (
    <CircleMarker
      center={toLatLng(point)}
      radius={kind === 'driver' ? 9 : 8}
      pathOptions={{ color: '#ffffff', weight: 3, fillColor: color, fillOpacity: 1 }}
    >
      <Tooltip>{label}</Tooltip>
    </CircleMarker>
  )
}

export function RouteLine({ route }: { route: RouteResult }) {
  return (
    <Polyline
      positions={routeToLatLngs(route)}
      pathOptions={{ color: '#171717', weight: 5, opacity: 0.8 }}
      attribution={ROUTE_ATTRIBUTION}
    />
  )
}

/** Fits the view to the given points whenever their set changes. */
export function FitToPoints({ points }: { points: Coordinates[] }) {
  const map = useMap()
  const key = points.map((p) => `${p.latitude},${p.longitude}`).join('|')

  useEffect(() => {
    if (points.length === 0) return
    if (points.length === 1 && points[0]) {
      map.setView(toLatLng(points[0]), Math.max(map.getZoom(), 14))
      return
    }
    map.fitBounds(latLngBounds(points.map(toLatLng)), { padding: [48, 48] })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` captures the points
  }, [map, key])

  return null
}

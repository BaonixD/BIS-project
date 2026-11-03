import type { LatLngTuple } from 'leaflet'
import type { Coordinates, RouteResult } from '@/api'

export const ALMATY_CENTER: Coordinates = { latitude: 43.238, longitude: 76.945 }
export const DEFAULT_ZOOM = 13

export function toLatLng(point: Coordinates): LatLngTuple {
  return [point.latitude, point.longitude]
}

export function fromLatLng(lat: number, lng: number): Coordinates {
  return { latitude: lat, longitude: lng }
}

export function routeToLatLngs(route: RouteResult): LatLngTuple[] {
  return route.route_geometry.coordinates.flatMap(([longitude, latitude]) =>
    longitude === undefined || latitude === undefined ? [] : [[latitude, longitude] as LatLngTuple],
  )
}

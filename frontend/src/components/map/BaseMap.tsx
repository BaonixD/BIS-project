import { useEffect, type ReactNode } from 'react'
import L from 'leaflet'
import { setWorkerUrl } from 'maplibre-gl'
import type { Map as MaplibreMap } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import 'maplibre-gl/dist/maplibre-gl.css'
import '@maplibre/maplibre-gl-leaflet'
import { MapContainer, useMap, useMapEvents } from 'react-leaflet'
import { cn } from '@/lib/utils'
import type { Coordinates } from '@/api'
import { ALMATY_CENTER, DEFAULT_ZOOM, fromLatLng, toLatLng } from '@/lib/geo'

// OpenFreeMap: free vector tiles without a key; Positron is the light Uber-like style.
const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'

setWorkerUrl(workerUrl)
const ATTRIBUTION =
  '<a href="https://openfreemap.org">OpenFreeMap</a> &copy; <a href="https://www.openmaptiles.org/">OpenMapTiles</a> ' +
  'Data from <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

// Positron, warmed towards the TezJet palette: steppe-light land, sky-blue water,
// sage parks and a faint gold casing on main roads. Labels and road geometry stay as they are.
type PaintProperty = Parameters<MaplibreMap['setPaintProperty']>[1]

const THEME: readonly [layer: string, property: PaintProperty, value: string][] = [
  ['background', 'background-color', '#f5f3ec'],
  ['road_area_pier', 'fill-color', '#f5f3ec'],
  ['road_pier', 'line-color', '#f5f3ec'],
  ['landuse_residential', 'fill-color', '#eeebe3'],
  ['building', 'fill-color', '#ebe7dd'],
  ['building', 'fill-outline-color', '#dfdacd'],
  ['park', 'fill-color', '#e1ebda'],
  ['landcover_wood', 'fill-color', '#d9e6d1'],
  ['water', 'fill-color', '#bfe4ec'],
  ['waterway', 'line-color', '#a5d6e2'],
  ['water_name_point_label', 'text-color', '#00788a'],
  ['water_name_line_label', 'text-color', '#00788a'],
  ['highway_major_casing', 'line-color', '#e8d9a8'],
  ['highway_motorway_casing', 'line-color', '#e2c97d'],
  ['highway_motorway_bridge_casing', 'line-color', '#e2c97d'],
  ['tunnel_motorway_casing', 'line-color', '#e8d9a8'],
]

function applyTheme(map: MaplibreMap) {
  for (const [layer, property, value] of THEME) {
    if (map.getLayer(layer)) map.setPaintProperty(layer, property, value)
  }
}

function VectorBasemap() {
  const map = useMap()
  useEffect(() => {
    const layer = L.maplibreGL({
      style: STYLE_URL,
      attributionControl: false,
    } as L.LeafletMaplibreGLOptions).addTo(map)
    const gl = layer.getMaplibreMap()
    const theme = () => applyTheme(gl)
    gl.on('style.load', theme)
    if (gl.isStyleLoaded()) theme()
    return () => {
      gl.off('style.load', theme)
      layer.remove()
    }
  }, [map])
  return null
}

function AttributionTopRight() {
  const map = useMap()
  useEffect(() => {
    // The map's own control, moved: layers (e.g. the route line) report their attribution to it.
    const control = map.attributionControl
    control?.setPosition('topright').setPrefix(false).addAttribution(ATTRIBUTION)
    return () => {
      control?.removeAttribution(ATTRIBUTION)
    }
  }, [map])
  return null
}

function ClickHandler({ onPick }: { onPick: (point: Coordinates) => void }) {
  useMapEvents({ click: (event) => onPick(fromLatLng(event.latlng.lat, event.latlng.lng)) })
  return null
}

interface BaseMapProps {
  className?: string
  center?: Coordinates
  zoom?: number
  onPick?: (point: Coordinates) => void
  children?: ReactNode
}

/** OpenFreeMap Positron basemap centred on Almaty; `isolate` keeps Leaflet z-indexes inside the map. */
export function BaseMap({
  className,
  center = ALMATY_CENTER,
  zoom = DEFAULT_ZOOM,
  onPick,
  children,
}: BaseMapProps) {
  return (
    <MapContainer
      center={toLatLng(center)}
      zoom={zoom}
      zoomControl={false}
      // Avoid delayed Leaflet CSS zoom callbacks after a ride screen unmounts.
      zoomAnimation={false}
      className={cn('isolate h-full w-full', className)}
    >
      <VectorBasemap />
      <AttributionTopRight />
      {onPick && <ClickHandler onPick={onPick} />}
      {children}
    </MapContainer>
  )
}

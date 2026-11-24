import { useEffect, useRef, type ReactNode } from 'react'
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
import { useNightMap } from '@/lib/map-theme'

// OpenFreeMap: free vector tiles without a key; Positron is the light Uber-like style.
const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'

setWorkerUrl(workerUrl)
const ATTRIBUTION =
  '<a href="https://openfreemap.org">OpenFreeMap</a> &copy; <a href="https://www.openmaptiles.org/">OpenMapTiles</a> ' +
  'Data from <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

type PaintProperty = Parameters<MaplibreMap['setPaintProperty']>[1]
type Palette = readonly [layer: string, property: PaintProperty, value: string][]

// Positron, warmed towards the TulparTaxi palette: steppe-light land, sky-blue water,
// sage parks and a faint gold casing on main roads. Labels and road geometry stay as they are.
const DAY: Palette = [
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

const NIGHT_INK = '#0f1b20'
const NIGHT_LABELS = [
  'label_other',
  'label_village',
  'label_town',
  'label_state',
  'label_city',
  'label_city_capital',
  'label_country_1',
  'label_country_2',
  'label_country_3',
  'airport',
  'highway-name-minor',
  'highway-name-major',
  'highway-name-path',
  'waterway_line_label',
]

// «Түнгі Алматы»: deep blue-green land, gold motorways and dim-gold avenues.
const NIGHT: Palette = [
  ['background', 'background-color', NIGHT_INK],
  ['road_area_pier', 'fill-color', NIGHT_INK],
  ['road_pier', 'line-color', NIGHT_INK],
  ['landuse_residential', 'fill-color', '#132228'],
  ['building', 'fill-color', '#182a30'],
  ['building', 'fill-outline-color', '#1f343b'],
  ['park', 'fill-color', '#12261f'],
  ['landcover_wood', 'fill-color', '#11241d'],
  ['landcover_ice_shelf', 'fill-color', '#1c2c31'],
  ['landcover_glacier', 'fill-color', '#1c2c31'],
  ['aeroway-area', 'fill-color', '#16262b'],
  ['aeroway-runway', 'line-color', '#243338'],
  ['aeroway-taxiway', 'line-color', '#203035'],
  ['aeroway-runway-casing', 'line-color', '#203035'],
  ['water', 'fill-color', '#0b3440'],
  ['waterway', 'line-color', '#12495a'],
  ['water_name_point_label', 'text-color', '#5fc6d8'],
  ['water_name_line_label', 'text-color', '#5fc6d8'],
  ['highway_path', 'line-color', '#1d2d32'],
  ['highway_minor', 'line-color', '#25363c'],
  ['highway_major_casing', 'line-color', '#3a3317'],
  ['highway_major_inner', 'line-color', '#8a7024'],
  ['highway_major_subtle', 'line-color', '#4a3f1a'],
  ['highway_motorway_casing', 'line-color', '#6b5410'],
  ['highway_motorway_inner', 'line-color', '#e0b12a'],
  ['highway_motorway_subtle', 'line-color', '#6b5410'],
  ['highway_motorway_bridge_casing', 'line-color', '#6b5410'],
  ['highway_motorway_bridge_inner', 'line-color', '#e0b12a'],
  ['tunnel_motorway_casing', 'line-color', '#3a3317'],
  ['tunnel_motorway_inner', 'line-color', '#5a4a1a'],
  ['railway', 'line-color', '#2a3a40'],
  ['railway_dashline', 'line-color', NIGHT_INK],
  ['railway_transit', 'line-color', '#2a3a40'],
  ['railway_transit_dashline', 'line-color', NIGHT_INK],
  ['railway_service', 'line-color', '#2a3a40'],
  ['railway_service_dashline', 'line-color', NIGHT_INK],
  ['boundary_2', 'line-color', '#3b4c52'],
  ['boundary_3', 'line-color', '#3b4c52'],
  ['boundary_disputed', 'line-color', '#3b4c52'],
  ...NIGHT_LABELS.flatMap((layer): Palette[number][] => [
    [layer, 'text-color', '#c9d4d6'],
    [layer, 'text-halo-color', NIGHT_INK],
  ]),
]

type Originals = Map<string, unknown>

/** The style's own values of every property a palette touches, read once per loaded style. */
function readOriginals(map: MaplibreMap): Originals {
  const originals: Originals = new Map()
  for (const [layer, property] of [...DAY, ...NIGHT]) {
    if (map.getLayer(layer)) originals.set(`${layer}|${property}`, map.getPaintProperty(layer, property))
  }
  return originals
}

/** Back to the style's values, then the palette on top, so switching never leaves stray colours. */
function applyTheme(map: MaplibreMap, palette: Palette, originals: Originals) {
  for (const [key, value] of originals) {
    const [layer = '', property = ''] = key.split('|')
    map.setPaintProperty(
      layer,
      property as PaintProperty,
      value as Parameters<MaplibreMap['setPaintProperty']>[2],
    )
  }
  for (const [layer, property, value] of palette) {
    if (map.getLayer(layer)) map.setPaintProperty(layer, property, value)
  }
}

function VectorBasemap({ night }: { night: boolean }) {
  const map = useMap()
  const palette = useRef<Palette>(night ? NIGHT : DAY)
  const repaint = useRef<(() => void) | null>(null)
  useEffect(() => {
    const layer = L.maplibreGL({
      style: STYLE_URL,
      attributionControl: false,
    } as L.LeafletMaplibreGLOptions).addTo(map)
    const gl = layer.getMaplibreMap()
    // isStyleLoaded() stays false while tiles and sprites load, so style.load marks readiness.
    let originals: Originals | null = null
    const paint = () => {
      if (originals) applyTheme(gl, palette.current, originals)
    }
    const loaded = () => {
      originals = readOriginals(gl)
      paint()
    }
    gl.on('style.load', loaded)
    if (gl.isStyleLoaded()) loaded()
    repaint.current = paint
    return () => {
      gl.off('style.load', loaded)
      repaint.current = null
      layer.remove()
    }
  }, [map])
  useEffect(() => {
    palette.current = night ? NIGHT : DAY
    repaint.current?.()
  }, [night])
  return null
}

/** Leaflet sizes itself once; a container that grows later (a card, a sheet) left grey tiles. */
function FollowContainerSize() {
  const map = useMap()
  useEffect(() => {
    const container = map.getContainer()
    if (typeof ResizeObserver === 'undefined') return
    let frame = 0
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => map.invalidateSize({ pan: false }))
    })
    observer.observe(container)
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
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
  const night = useNightMap()
  return (
    <MapContainer
      center={toLatLng(center)}
      zoom={zoom}
      zoomControl={false}
      // Avoid delayed Leaflet CSS zoom callbacks after a ride screen unmounts.
      zoomAnimation={false}
      className={cn('isolate h-full w-full', night && 'map-night', className)}
    >
      <VectorBasemap night={night} />
      <FollowContainerSize />
      <AttributionTopRight />
      {onPick && <ClickHandler onPick={onPick} />}
      {children}
    </MapContainer>
  )
}

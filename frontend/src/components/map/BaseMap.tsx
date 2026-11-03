import { useEffect, type ReactNode } from 'react'
import L from 'leaflet'
import { setWorkerUrl } from 'maplibre-gl'
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

function VectorBasemap() {
  const map = useMap()
  useEffect(() => {
    const layer = L.maplibreGL({ style: STYLE_URL, attributionControl: false } as L.LeafletMaplibreGLOptions).addTo(map)
    return () => {
      layer.remove()
    }
  }, [map])
  return null
}

function AttributionTopRight() {
  const map = useMap()
  useEffect(() => {
    // The map's own control, moved: layers (e.g. the openrouteservice route) report their attribution to it.
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
export function BaseMap({ className, center = ALMATY_CENTER, zoom = DEFAULT_ZOOM, onPick, children }: BaseMapProps) {
  return (
    <MapContainer
      center={toLatLng(center)}
      zoom={zoom}
      zoomControl={false}
      className={cn('isolate h-full w-full', className)}
    >
      <VectorBasemap />
      <AttributionTopRight />
      {onPick && <ClickHandler onPick={onPick} />}
      {children}
    </MapContainer>
  )
}

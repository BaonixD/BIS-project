import type { ReactNode } from 'react'
import { MapContainer, TileLayer, useMapEvents } from 'react-leaflet'
import { cn } from '@/lib/utils'
import type { Coordinates } from '@/api'
import { ALMATY_CENTER, DEFAULT_ZOOM, fromLatLng, toLatLng } from '@/lib/geo'

const TILE_URL = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors ' +
  '&copy; <a href="https://carto.com/attributions">CARTO</a>'

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

/** CARTO Positron basemap centred on Almaty; `isolate` keeps Leaflet z-indexes inside the map. */
export function BaseMap({ className, center = ALMATY_CENTER, zoom = DEFAULT_ZOOM, onPick, children }: BaseMapProps) {
  return (
    <MapContainer
      center={toLatLng(center)}
      zoom={zoom}
      zoomControl={false}
      className={cn('isolate h-full w-full', className)}
    >
      <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} subdomains="abcd" maxZoom={20} />
      {onPick && <ClickHandler onPick={onPick} />}
      {children}
    </MapContainer>
  )
}

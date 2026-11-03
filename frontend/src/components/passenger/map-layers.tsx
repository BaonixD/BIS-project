import { useEffect } from 'react'
import { Marker, useMap, useMapEvents } from 'react-leaflet'
import { divIcon } from 'leaflet'
import type { Coordinates } from '@/api'
import centerPinUrl from '@/assets/passenger/center-pin.svg'
import pulseUrl from '@/assets/passenger/search-pulse.svg'
import { fromLatLng, toLatLng } from '@/lib/geo'

/** Figma «Pulse» 5:332: 200px halo around the pickup while a driver is searched. */
const pulseIcon = divIcon({
  className: 'map-marker',
  html: `<img src="${pulseUrl}" width="200" height="200" alt="" class="block" draggable="false" />`,
  iconSize: [200, 200],
  iconAnchor: [100, 100],
})

export function PulseMarker({ point }: { point: Coordinates }) {
  return <Marker position={toLatLng(point)} icon={pulseIcon} interactive={false} keyboard={false} zIndexOffset={500} />
}

/**
 * Figma «CenterPin» 23:169: 40×64 at y=300 of the frame, i.e. 253px under the page top, tip at y=61.
 * The tip marks the centre of the map, so on mobile the map is 2 × 314px tall (`PIN_MAP_HEIGHT`)
 * and its lower part hides under the sheet.
 */
export const PIN_MAP_CLASS = 'max-lg:bottom-auto max-lg:h-[628px]'

export function CenterPin() {
  return (
    <img
      src={centerPinUrl}
      width={40}
      height={64}
      alt=""
      aria-hidden
      draggable={false}
      className="pointer-events-none absolute top-[253px] left-1/2 z-20 -ml-5 block lg:top-[calc(50%-61px)]"
    />
  )
}

/** Puts `start` under the pin on mount and reports the map centre (the pin tip) after each move. */
export function PinTracker({ start, onChange }: { start: Coordinates; onChange: (point: Coordinates) => void }) {
  const map = useMap()

  const report = () => {
    const center = map.getCenter()
    onChange(fromLatLng(center.lat, center.lng))
  }

  useMapEvents({ moveend: report })

  useEffect(() => {
    map.setView(toLatLng(start), Math.max(map.getZoom(), 16), { animate: false })
    report()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on mount
  }, [map])

  return null
}

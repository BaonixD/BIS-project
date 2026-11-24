import { useEffect } from 'react'
import { Marker, useMap, useMapEvents } from 'react-leaflet'
import { divIcon } from 'leaflet'
import type { Coordinates } from '@/api'
import centerPinUrl from '@/assets/passenger/center-pin.svg'
import { fromLatLng, toLatLng } from '@/lib/geo'

const UYKS = 24
const GLOW_S = 2.4

/** The yurt's crown (шаңырақ): a ring, the crossed күлдіреуіш and 24 roof poles (уық). */
function shanyrakSvg(): string {
  const poles = Array.from({ length: UYKS }, (_, index) => {
    const angle = (index / UYKS) * Math.PI * 2
    const x = (radius: number) => (100 + radius * Math.cos(angle)).toFixed(1)
    const y = (radius: number) => (100 + radius * Math.sin(angle)).toFixed(1)
    const delay = (-(index / UYKS) * GLOW_S).toFixed(2)
    return `<line x1="${x(42)}" y1="${y(42)}" x2="${x(86)}" y2="${y(86)}" class="shanyrak-uyk" style="animation-delay:${delay}s" />`
  }).join('')
  const bars = [-11, 11]
    .flatMap((offset) => {
      const half = Math.sqrt(34 * 34 - offset * offset).toFixed(1)
      const bend = (100 + offset * 1.9).toFixed(1)
      const line = (100 + offset).toFixed(1)
      return [
        `M${line} ${(100 - Number(half)).toFixed(1)}Q${bend} 100 ${line} ${(100 + Number(half)).toFixed(1)}`,
        `M${(100 - Number(half)).toFixed(1)} ${line}Q100 ${bend} ${(100 + Number(half)).toFixed(1)} ${line}`,
      ]
    })
    .join('')
  return (
    '<svg width="200" height="200" viewBox="0 0 200 200" class="block" aria-hidden="true">' +
    '<circle cx="100" cy="100" r="96" fill="#00afca" fill-opacity="0.08" />' +
    '<g class="shanyrak-spin">' +
    `<g stroke-width="3.5" stroke-linecap="round">${poles}</g>` +
    '<circle cx="100" cy="100" r="37" fill="#fff" stroke="#000" stroke-width="4" />' +
    `<path d="${bars}" fill="none" stroke="#000" stroke-width="3" stroke-linecap="round" />` +
    '</g></svg>'
  )
}

/** Instead of Figma «Pulse» 5:332: the turning шаңырақ over the pickup while a driver is searched. */
const pulseIcon = divIcon({
  className: 'map-marker',
  html: shanyrakSvg(),
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
      className="pointer-events-none absolute top-[253px] left-1/2 z-20 -ml-5 block lg:top-[calc(50%-61px)] dark:invert"
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

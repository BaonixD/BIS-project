import { Polyline } from 'react-leaflet'
import type { Coordinates } from '@/api'
import { toLatLng } from '@/lib/geo'

/** Figma New offer (6:189): black dotted line from the driver to the pickup. */
export function DashedLine({ from, to }: { from: Coordinates; to: Coordinates }) {
  return (
    <Polyline
      positions={[toLatLng(from), toLatLng(to)]}
      pathOptions={{ color: '#000000', weight: 4, opacity: 1, dashArray: '0 9', lineCap: 'round' }}
    />
  )
}

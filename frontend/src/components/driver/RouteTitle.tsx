import type { Coordinates } from '@/api'
import { useReverseGeocode } from '@/hooks/use-geocoding'

/** «Абая 52 → Esentai Mall» from the ride points (Nominatim, cached, one request a second). */
export function RouteTitle({ pickup, dropoff }: { pickup: Coordinates; dropoff: Coordinates }) {
  const from = useReverseGeocode(pickup)
  const to = useReverseGeocode(dropoff)
  return (
    <>
      {from.data?.title ?? '…'} → {to.data?.title ?? '…'}
    </>
  )
}

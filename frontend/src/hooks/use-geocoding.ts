import { useQuery } from '@tanstack/react-query'
import type { Coordinates } from '@/api'
import { geocoder, MIN_QUERY_LENGTH, SEARCH_DEBOUNCE_MS, useDebouncedValue } from '@/lib/geocoding'

/** Address suggestions for a typed query, debounced by 600 ms (Nominatim forbids per-keystroke requests). */
export function useAddressSearch(query: string) {
  const debounced = useDebouncedValue(query.trim(), SEARCH_DEBOUNCE_MS)
  return useQuery({
    queryKey: ['geocoding', 'search', debounced.toLowerCase()],
    queryFn: ({ signal }) => geocoder.search(debounced, signal),
    enabled: debounced.length >= MIN_QUERY_LENGTH,
    staleTime: Infinity,
    retry: false,
  })
}

/** Address of a map point; resolves to «Точка на карте» + coordinates when Nominatim fails. */
export function useReverseGeocode(point: Coordinates | null) {
  return useQuery({
    queryKey: ['geocoding', 'reverse', point?.latitude.toFixed(5), point?.longitude.toFixed(5)],
    queryFn: ({ signal }) => geocoder.reverse(point as Coordinates, signal),
    enabled: point !== null,
    staleTime: Infinity,
    retry: false,
  })
}

import { useEffect, useState } from 'react'
import type { Coordinates } from '@/api'

/**
 * Address search and reverse geocoding through OpenStreetMap Nominatim.
 * Usage policy: at most one request per second, cache results, no autocomplete per keystroke
 * (callers debounce by ≥ SEARCH_DEBOUNCE_MS). https://operations.osmfoundation.org/policies/nominatim/
 */

export const NOMINATIM_URL = 'https://nominatim.openstreetmap.org'
export const SEARCH_DEBOUNCE_MS = 600
export const MIN_QUERY_LENGTH = 3
export const FALLBACK_TITLE = 'Точка на карте'
/** Almaty: left, top, right, bottom (lon, lat). */
const ALMATY_VIEWBOX = '76.75,43.41,77.15,43.12'
const MIN_INTERVAL_MS = 1000
const RESULT_LIMIT = 6

export interface Place {
  id: string
  title: string
  subtitle: string
  point: Coordinates
}

interface NominatimAddress {
  road?: string
  pedestrian?: string
  house_number?: string
  suburb?: string
  city_district?: string
  city?: string
}

interface NominatimPlace {
  place_id: number
  lat: string
  lon: string
  name?: string
  display_name: string
  address?: NominatimAddress
}

export interface GeocoderOptions {
  fetch?: typeof fetch
  now?: () => number
  sleep?: (ms: number) => Promise<void>
  minIntervalMs?: number
}

function coordinateKey(point: Coordinates): string {
  return `${point.latitude.toFixed(5)},${point.longitude.toFixed(5)}`
}

export function fallbackPlace(point: Coordinates): Place {
  return {
    id: coordinateKey(point),
    title: FALLBACK_TITLE,
    subtitle: `${point.latitude.toFixed(5)}, ${point.longitude.toFixed(5)}`,
    point,
  }
}

function street(address: NominatimAddress): string {
  return [address.road ?? address.pedestrian, address.house_number].filter(Boolean).join(', ')
}

function toPlace(raw: NominatimPlace): Place {
  const address = raw.address ?? {}
  const streetLine = street(address)
  const area = address.suburb ?? address.city_district ?? address.city ?? ''
  const name = raw.name?.trim()
  const title = name || streetLine || raw.display_name.split(', ')[0] || FALLBACK_TITLE
  const subtitle = name && streetLine ? streetLine : area
  return {
    id: String(raw.place_id),
    title,
    subtitle,
    point: { latitude: Number(raw.lat), longitude: Number(raw.lon) },
  }
}

function isNominatimPlace(value: unknown): value is NominatimPlace {
  return typeof value === 'object' && value !== null && 'lat' in value && 'lon' in value && 'place_id' in value
}

/** Runs tasks one at a time, starting each at least `intervalMs` after the previous one. */
function createThrottle(intervalMs: number, now: () => number, sleep: (ms: number) => Promise<void>) {
  let lastStart = Number.NEGATIVE_INFINITY
  let queue: Promise<unknown> = Promise.resolve()
  return <T>(task: () => Promise<T>): Promise<T> => {
    const run = queue.then(async () => {
      const wait = lastStart + intervalMs - now()
      if (wait > 0) await sleep(wait)
      lastStart = now()
      return task()
    })
    queue = run.catch(() => undefined)
    return run
  }
}

export function createGeocoder({
  fetch: fetchImpl = (...args) => globalThis.fetch(...args),
  now = Date.now,
  sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  minIntervalMs = MIN_INTERVAL_MS,
}: GeocoderOptions = {}) {
  const throttle = createThrottle(minIntervalMs, now, sleep)
  const searches = new Map<string, Place[]>()
  const reverses = new Map<string, Place>()

  async function request(path: 'search' | 'reverse', params: Record<string, string>, signal?: AbortSignal) {
    const url = new URL(`${NOMINATIM_URL}/${path}`)
    const query = { format: 'jsonv2', 'accept-language': 'ru', addressdetails: '1', ...params }
    Object.entries(query).forEach(([key, value]) => url.searchParams.set(key, value))
    return throttle(async () => {
      signal?.throwIfAborted()
      const response = await fetchImpl(url.toString(), { signal, headers: { Accept: 'application/json' } })
      if (!response.ok) throw new Error(`Nominatim ${path} failed: ${response.status}`)
      return (await response.json()) as unknown
    })
  }

  async function search(query: string, signal?: AbortSignal): Promise<Place[]> {
    const key = query.trim().toLowerCase()
    if (key.length < MIN_QUERY_LENGTH) return []
    const cached = searches.get(key)
    if (cached) return cached
    const body = await request(
      'search',
      { q: query.trim(), viewbox: ALMATY_VIEWBOX, bounded: '1', countrycodes: 'kz', limit: String(RESULT_LIMIT) },
      signal,
    )
    const places = Array.isArray(body) ? body.filter(isNominatimPlace).map(toPlace) : []
    searches.set(key, places)
    return places
  }

  /** Never rejects: an unknown point becomes «Точка на карте» with its coordinates. */
  async function reverse(point: Coordinates, signal?: AbortSignal): Promise<Place> {
    const key = coordinateKey(point)
    const cached = reverses.get(key)
    if (cached) return cached
    try {
      const body = await request(
        'reverse',
        { lat: String(point.latitude), lon: String(point.longitude), zoom: '18' },
        signal,
      )
      if (!isNominatimPlace(body)) return fallbackPlace(point)
      const place = { ...toPlace(body), id: key, point }
      reverses.set(key, place)
      return place
    } catch {
      return fallbackPlace(point)
    }
  }

  return { search, reverse }
}

export type Geocoder = ReturnType<typeof createGeocoder>

export const geocoder = createGeocoder()

export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

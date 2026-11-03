import type { Place } from '@/lib/geocoding'

const STORAGE_KEY = 'bis.recentPlaces'
const LIMIT = 2

/** Shown until the passenger has own recent destinations (Figma Home 4:94). */
export const POPULAR_PLACES: Place[] = [
  {
    id: 'popular-mega',
    title: 'Mega Alma-Ata',
    subtitle: 'пр. Розыбакиева, 247А',
    point: { latitude: 43.20187, longitude: 76.89207 },
  },
  {
    id: 'popular-esentai',
    title: 'Esentai Mall',
    subtitle: 'пр. Аль-Фараби, 77/8',
    point: { latitude: 43.21834, longitude: 76.92763 },
  },
]

function isPlace(value: unknown): value is Place {
  const place = value as Place | null
  return (
    typeof place?.title === 'string' &&
    typeof place.point?.latitude === 'number' &&
    typeof place.point?.longitude === 'number'
  )
}

export function readRecentPlaces(storage: Storage = localStorage): Place[] {
  try {
    const parsed: unknown = JSON.parse(storage.getItem(STORAGE_KEY) ?? '[]')
    return Array.isArray(parsed) ? parsed.filter(isPlace) : []
  } catch {
    return []
  }
}

export function rememberPlace(place: Place, storage: Storage = localStorage): void {
  const same = (other: Place) => other.title === place.title && other.subtitle === place.subtitle
  const next = [place, ...readRecentPlaces(storage).filter((other) => !same(other))].slice(0, LIMIT)
  storage.setItem(STORAGE_KEY, JSON.stringify(next))
}

/** Recent destinations first, then popular places, two rows in total. */
export function suggestedPlaces(recent: Place[]): Place[] {
  const titles = new Set(recent.map((place) => place.title))
  return [...recent, ...POPULAR_PLACES.filter((place) => !titles.has(place.title))].slice(0, LIMIT)
}

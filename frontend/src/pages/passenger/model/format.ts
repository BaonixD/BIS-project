import type { Coordinates } from '@/api'

const TIME_ZONE = 'Asia/Almaty'

const clockFormat = new Intl.DateTimeFormat('ru-RU', { timeZone: TIME_ZONE, hour: '2-digit', minute: '2-digit' })
const dayMonthFormat = new Intl.DateTimeFormat('ru-RU', { timeZone: TIME_ZONE, day: 'numeric', month: 'long' })
const dayKeyFormat = new Intl.DateTimeFormat('en-CA', { timeZone: TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit' })

const amountFormat = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })

/** «2 200 ₸» with ordinary spaces, as in the mockups (Intl may print «KZT» instead of the sign). */
export function formatPrice(amountKzt: number): string {
  return `${amountFormat.format(amountKzt).replace(/\s/g, ' ')} ₸`
}

/** «10,0 км». */
export function formatKm(distanceM: number): string {
  return `${(distanceM / 1000).toFixed(1).replace('.', ',')} км`
}

/** «10 км», «4,1 км»: no trailing «,0». */
export function formatKmCompact(distanceM: number): string {
  return formatKm(distanceM).replace(',0 ', ' ')
}

export function formatMinutes(durationS: number): string {
  return `${Math.max(1, Math.round(durationS / 60))} мин`
}

/** «14:20» in Almaty time. */
export function formatClock(iso: string | number | Date): string {
  return clockFormat.format(new Date(iso))
}

/** «3 ноября, 14:20». */
export function formatRideDate(iso: string): string {
  return `${dayMonthFormat.format(new Date(iso))}, ${formatClock(iso)}`
}

/** «СЕГОДНЯ», «ВЧЕРА» or «1 НОЯБРЯ» for history groups. */
export function historyDayLabel(iso: string, now: number = Date.now()): string {
  const day = dayKeyFormat.format(new Date(iso))
  if (day === dayKeyFormat.format(new Date(now))) return 'СЕГОДНЯ'
  if (day === dayKeyFormat.format(new Date(now - 86_400_000))) return 'ВЧЕРА'
  return dayMonthFormat.format(new Date(iso)).toUpperCase()
}

/** «02:45». */
export function formatCountdown(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds))
  return `${String(Math.floor(safe / 60)).padStart(2, '0')}:${String(safe % 60).padStart(2, '0')}`
}

const EARTH_RADIUS_M = 6_371_000

export function distanceMeters(a: Coordinates, b: Coordinates): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180
  const dLat = toRad(b.latitude - a.latitude)
  const dLon = toRad(b.longitude - a.longitude)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.latitude)) * Math.cos(toRad(b.latitude)) * Math.sin(dLon / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h))
}

/** City driving speed for the pickup estimate (no traffic data in the MVP). */
const CITY_SPEED_MPS = 25_000 / 3600
/** Straight line → road distance. */
const ROAD_FACTOR = 1.3

/** Rough minutes for the driver to reach the pickup, at least 1. */
export function pickupEtaMinutes(driver: Coordinates, pickup: Coordinates): number {
  return Math.max(1, Math.round((distanceMeters(driver, pickup) * ROAD_FACTOR) / CITY_SPEED_MPS / 60))
}

/** Share of `total` seconds elapsed since `since`, clamped to 0..1. */
export function elapsedShare(since: string | null | undefined, totalS: number, now: number = Date.now()): number {
  if (!since || totalS <= 0) return 0
  return Math.min(1, Math.max(0, (now - Date.parse(since)) / 1000 / totalS))
}

/** «Арман Нурланов» → «Арман Н.». */
export function shortName(fullName: string | null | undefined): string {
  const [first, second] = (fullName ?? '').trim().split(/\s+/)
  if (!first) return 'Водитель'
  return second ? `${first} ${second.charAt(0)}.` : first
}

/** «с Арманом»: instrumental case of a first name (common Russian/Kazakh endings). */
export function withName(fullName: string | null | undefined): string {
  const first = (fullName ?? '').trim().split(/\s+/)[0]
  if (!first) return 'с водителем'
  const last = first.slice(-1).toLowerCase()
  if (last === 'й') return `с ${first.slice(0, -1)}ем`
  if (last === 'а') return `с ${first.slice(0, -1)}ой`
  if (last === 'я') return `с ${first.slice(0, -1)}ей`
  if (/[бвгджзклмнпрстфхцчшщ]/.test(last)) return `с ${first}ом`
  return `с ${first}`
}

export function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase())
    .join('')
}

import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createGeocoder, SEARCH_DEBOUNCE_MS, useDebouncedValue } from './geocoding'

const ESENTAI = {
  place_id: 1,
  lat: '43.2185',
  lon: '76.9282',
  name: 'Esentai Mall',
  display_name: 'Esentai Mall, 77/8, проспект Аль-Фараби, Бостандыкский район, Алматы, Казахстан',
  address: { road: 'проспект Аль-Фараби', house_number: '77/8', city: 'Алматы' },
}

const ABAYA = {
  place_id: 2,
  lat: '43.2399',
  lon: '76.9150',
  name: '',
  display_name: '52, проспект Абая, Алмалинский район, Алматы, Казахстан',
  address: { road: 'проспект Абая', house_number: '52', city_district: 'Алмалинский район', city: 'Алматы' },
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

/** A geocoder on a virtual clock: `sleep` advances time instantly and records each wait. */
function setup(respond: (url: URL) => Response | Promise<Response>) {
  let time = 0
  const waits: number[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => respond(new URL(String(input))))
  const geocoder = createGeocoder({
    fetch: fetchMock as unknown as typeof fetch,
    now: () => time,
    sleep: async (ms) => {
      waits.push(ms)
      time += ms
    },
  })
  return { geocoder, fetchMock, waits, advance: (ms: number) => (time += ms) }
}

describe('geocoder.search', () => {
  it('queries Nominatim within the Almaty viewbox in Russian', async () => {
    const { geocoder, fetchMock } = setup(() => json([ESENTAI]))
    const places = await geocoder.search('esentai')
    const url = new URL(String(fetchMock.mock.calls[0]?.[0]))
    expect(url.origin + url.pathname).toBe('https://nominatim.openstreetmap.org/search')
    expect(url.searchParams.get('q')).toBe('esentai')
    expect(url.searchParams.get('format')).toBe('jsonv2')
    expect(url.searchParams.get('bounded')).toBe('1')
    expect(url.searchParams.get('accept-language')).toBe('ru')
    expect(url.searchParams.get('viewbox')).toBe('76.55,43.45,77.3,43.05')
    expect(places).toEqual([
      {
        id: '1',
        title: 'Esentai Mall',
        subtitle: 'проспект Аль-Фараби, 77/8',
        point: { latitude: 43.2185, longitude: 76.9282 },
      },
    ])
  })

  it('names an address by its street and house when the place has no name', async () => {
    const { geocoder } = setup(() => json([ABAYA]))
    const [place] = await geocoder.search('абая 52')
    expect(place?.title).toBe('проспект Абая, 52')
    expect(place?.subtitle).toBe('Алмалинский район')
  })

  it('shows one row for a place mapped twice in OpenStreetMap (a node and its building)', async () => {
    const building = { ...ESENTAI, place_id: 3, lat: '43.2183', lon: '76.9280' }
    const { geocoder } = setup(() => json([ESENTAI, building, ABAYA]))
    const places = await geocoder.search('esentai')
    expect(places.map((place) => place.id)).toEqual(['1', '2'])
  })

  it('serves a repeated query from the cache', async () => {
    const { geocoder, fetchMock } = setup(() => json([ESENTAI]))
    await geocoder.search('Esentai')
    await geocoder.search('  esentai ')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('skips the network for queries shorter than three characters', async () => {
    const { geocoder, fetchMock } = setup(() => json([ESENTAI]))
    expect(await geocoder.search('es')).toEqual([])
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('sends at most one request per second', async () => {
    const { geocoder, fetchMock, waits } = setup(() => json([ESENTAI]))
    await Promise.all([geocoder.search('esentai'), geocoder.search('mega'), geocoder.search('dostyk')])
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(waits).toEqual([1000, 1000])
  })

  it('does not wait when the previous request is older than a second', async () => {
    const { geocoder, waits, advance } = setup(() => json([ESENTAI]))
    await geocoder.search('esentai')
    advance(1500)
    await geocoder.search('mega')
    expect(waits).toEqual([])
  })

  it('rejects on a failed request and does not cache the failure', async () => {
    let fail = true
    const { geocoder, fetchMock } = setup(() => (fail ? json({}, 503) : json([ESENTAI])))
    await expect(geocoder.search('esentai')).rejects.toThrow()
    fail = false
    await expect(geocoder.search('esentai')).resolves.toHaveLength(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})

describe('geocoder.reverse', () => {
  const point = { latitude: 43.2185, longitude: 76.9282 }

  it('turns a point into a place', async () => {
    const { geocoder, fetchMock } = setup(() => json(ESENTAI))
    const place = await geocoder.reverse(point)
    const url = new URL(String(fetchMock.mock.calls[0]?.[0]))
    expect(url.pathname).toBe('/reverse')
    expect(url.searchParams.get('lat')).toBe('43.2185')
    expect(url.searchParams.get('lon')).toBe('76.9282')
    expect(url.searchParams.get('accept-language')).toBe('ru')
    expect(place).toMatchObject({ title: 'Esentai Mall', point })
  })

  it('caches by rounded coordinates', async () => {
    const { geocoder, fetchMock } = setup(() => json(ESENTAI))
    await geocoder.reverse(point)
    await geocoder.reverse({ latitude: 43.218501, longitude: 76.928199 })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['a network error', () => Promise.reject(new TypeError('offline'))],
    ['an HTTP error', () => json({}, 500)],
    ['an empty answer', () => json({ error: 'Unable to geocode' })],
  ])('falls back to «Точка на карте» on %s', async (_case, respond) => {
    const { geocoder } = setup(respond)
    await expect(geocoder.reverse(point)).resolves.toEqual({
      id: '43.21850,76.92820',
      title: 'Точка на карте',
      subtitle: '43.21850, 76.92820',
      point,
    })
  })
})

describe('useDebouncedValue', () => {
  afterEach(() => vi.useRealTimers())

  it('waits at least 600 ms after the last change', () => {
    vi.useFakeTimers()
    expect(SEARCH_DEBOUNCE_MS).toBeGreaterThanOrEqual(600)
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, SEARCH_DEBOUNCE_MS), {
      initialProps: { value: 'e' },
    })
    rerender({ value: 'es' })
    act(() => vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS - 1))
    expect(result.current).toBe('e')
    rerender({ value: 'ese' })
    act(() => vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS - 1))
    expect(result.current).toBe('e')
    act(() => vi.advanceTimersByTime(1))
    expect(result.current).toBe('ese')
  })
})

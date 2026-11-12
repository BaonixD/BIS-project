import { render, waitFor } from '@testing-library/react'
import { Browser } from 'leaflet'
import { MapContainer } from 'react-leaflet'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import type { RouteResult } from '@/api'
import { RouteLine } from './layers'

// jsdom has SVG elements but does not advertise SVG rendering to Leaflet.
const originalSvg = Browser.svg
beforeAll(() => {
  Object.defineProperty(Browser, 'svg', { value: true })
})
afterAll(() => {
  Object.defineProperty(Browser, 'svg', { value: originalSvg })
})

const route: RouteResult = {
  distance_m: 2000,
  duration_s: 300,
  provider: 'osrm',
  route_geometry: {
    type: 'LineString',
    coordinates: [
      [76.945, 43.238],
      [76.95, 43.24],
      [76.96, 43.245],
    ],
  },
}

function mapWithRoute(value: RouteResult) {
  return (
    <MapContainer center={[43.238, 76.945]} zoom={13}>
      <RouteLine route={value} />
    </MapContainer>
  )
}

describe('route reveal lifecycle', () => {
  it('keeps the same path when polling returns an identical route in a new object', async () => {
    const view = render(mapWithRoute(route))
    await waitFor(() => expect(view.container.querySelector('.bis-route-line')).not.toBeNull())
    const path = view.container.querySelector('.bis-route-line')!
    expect(path.getAttribute('pathLength')).toBe('1')
    view.rerender(mapWithRoute(structuredClone({ ...route, duration_s: 320 })))
    expect(view.container.querySelector('.bis-route-line')).toBe(path)
    expect(view.container.textContent).toContain('OSRM')
  })

  it('creates a new reveal when the actual route geometry changes', async () => {
    const view = render(mapWithRoute(route))
    await waitFor(() => expect(view.container.querySelector('.bis-route-line')).not.toBeNull())
    const path = view.container.querySelector('.bis-route-line')!
    view.rerender(
      mapWithRoute({
        ...route,
        route_geometry: {
          type: 'LineString',
          coordinates: [
            [76.945, 43.238],
            [76.97, 43.25],
          ],
        },
      }),
    )
    const updated = view.container.querySelector('.bis-route-line')!
    expect(updated).not.toBe(path)
    expect(updated.getAttribute('pathLength')).toBe('1')
    expect(path.isConnected).toBe(false)
  })
})

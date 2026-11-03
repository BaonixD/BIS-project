import { describe, expect, it } from 'vitest'
import { routeAttribution } from './attribution'

const text = (html: string | undefined) => html?.replace(/<[^>]+>/g, '').replaceAll('&copy;', '©')

describe('routeAttribution', () => {
  it('credits OSRM and OpenStreetMap for a route from the own OSRM server', () => {
    expect(text(routeAttribution('osrm'))).toBe('Маршрут © OSRM, данные © OpenStreetMap')
    expect(routeAttribution('osrm')).toContain('href="https://project-osrm.org/"')
    expect(routeAttribution('osrm')).toContain('href="https://www.openstreetmap.org/copyright"')
  })

  it('keeps the HeiGIT credit for openrouteservice routes', () => {
    expect(text(routeAttribution('openrouteservice'))).toBe('Маршрут © openrouteservice.org by HeiGIT')
  })

  it('does not credit openrouteservice for a route it did not build', () => {
    expect(routeAttribution('osrm')).not.toContain('openrouteservice')
    expect(routeAttribution('fake')).toBeUndefined()
  })
})

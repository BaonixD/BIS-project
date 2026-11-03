const ROUTE_ATTRIBUTIONS = new Map([
  [
    'osrm',
    'Маршрут &copy; <a href="https://project-osrm.org/">OSRM</a>, ' +
      'данные &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  ],
  ['openrouteservice', 'Маршрут &copy; <a href="https://openrouteservice.org/">openrouteservice.org</a> by HeiGIT'],
])

/** Credit line for the service that built the route (`route.provider`); none for unknown ones. */
export function routeAttribution(provider: string): string | undefined {
  return ROUTE_ATTRIBUTIONS.get(provider)
}

import { t } from '@/i18n/core'
const ROUTE_ATTRIBUTIONS = () =>
  new Map([
    [
      'mapbox',
      t('Маршрут') +
        ' &copy; <a href="https://www.mapbox.com/about/maps/">Mapbox</a>, &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    ],
    [
      'osrm',
      t('Маршрут &copy; <a href="https://project-osrm.org/">OSRM</a>, ') +
        t('данные &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'),
    ],
    [
      'openrouteservice',
      t(
        'Маршрут &copy; <a href="https://openrouteservice.org/">openrouteservice.org</a> by HeiGIT',
      ),
    ],
  ])
/** Credit line for the service that built the route (`route.provider`); none for unknown ones. */
export function routeAttribution(provider: string): string | undefined {
  return ROUTE_ATTRIBUTIONS().get(provider)
}

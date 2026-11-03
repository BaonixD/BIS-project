import { errorMessage, isApiError } from '@/api'

const PASSENGER_MESSAGES: Record<string, string> = {
  rating_already_exists: 'Вы уже оценили эту поездку.',
  ride_not_completed: 'Оценить можно только завершённую поездку.',
  kaspi_unavailable: 'Оплата через Kaspi сейчас недоступна. Выберите наличные.',
}

/** The shared dictionary plus codes of the next passenger contract. */
export function passengerErrorMessage(error: unknown): string {
  if (isApiError(error) && PASSENGER_MESSAGES[error.code]) return PASSENGER_MESSAGES[error.code] as string
  return errorMessage(error)
}

const ROUTING_CODES = new Set(['routing_unavailable', 'routing_provider_error', 'network_error'])

/** Figma 24:897 text for an unavailable routing service; other errors use the dictionary. */
export function routeErrorText(error: unknown): string {
  if (isApiError(error) && ROUTING_CODES.has(error.code)) {
    return 'Сервис маршрутов сейчас недоступен. Попробуйте ещё раз через минуту.'
  }
  return passengerErrorMessage(error)
}

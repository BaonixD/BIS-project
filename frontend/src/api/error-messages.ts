import { ApiError } from './errors'

const MESSAGES: Record<string, string> = {
  network_error: 'Нет связи с сервером. Проверьте подключение и попробуйте ещё раз.',
  unknown_error: 'Сервер ответил неожиданно. Попробуйте ещё раз.',
  internal_error: 'Внутренняя ошибка сервера. Попробуйте позже.',
  validation_error: 'Проверьте введённые данные.',
  not_found: 'Запрошенный ресурс не найден.',
  method_not_allowed: 'Действие недоступно.',

  not_authenticated: 'Сессия истекла. Войдите снова.',
  invalid_credentials: 'Неверный логин или пароль.',
  too_many_attempts: 'Слишком много попыток входа. Подождите и попробуйте снова.',
  username_taken: 'Это имя пользователя уже занято.',
  invalid_google_token: 'Google не подтвердил вход. Попробуйте ещё раз.',
  google_login_unavailable: 'Вход через Google сейчас недоступен.',
  csrf_failed: 'Сессия устарела. Обновите страницу.',
  origin_not_allowed: 'Адрес приложения не разрешён на сервере (CORS_ALLOWED_ORIGINS).',
  account_blocked: 'Аккаунт заблокирован. Обратитесь к администратору.',
  user_not_found: 'Пользователь не найден.',
  admin_account_protected: 'Аккаунт администратора нельзя заблокировать.',
  account_has_active_ride: 'Сначала завершите активную поездку и подтвердите получение наличных.',
  forbidden: 'Недостаточно прав для этого действия.',

  driver_not_found: 'Водитель не найден.',
  driver_profile_incomplete: 'Профиль водителя заполнен не полностью.',
  driver_category_not_allowed: 'Выберите хотя бы один тариф, доступный классу вашей машины.',
  driver_not_approved: 'Водитель ещё не допущен администратором.',
  driver_on_active_ride: 'Сначала завершите текущую поездку.',
  driver_busy: 'У вас уже есть активная поездка.',
  plate_number_taken: 'Этот госномер уже зарегистрирован у другого водителя.',

  route_points_identical: 'Точки посадки и назначения совпадают.',
  route_not_found: 'Между выбранными точками нет дорожного маршрута.',
  routing_unavailable: 'Построение маршрута сейчас недоступно на сервере.',
  routing_provider_error: 'Сервис маршрутов не ответил. Попробуйте чуть позже.',

  quote_not_found: 'Расчёт цены не найден. Запросите цену заново.',
  quote_expired: 'Цена устарела. Запросите новую.',
  quote_already_used: 'Этот расчёт уже использован. Запросите новую цену.',
  active_ride_exists: 'У вас уже есть активная поездка.',
  idempotency_key_required: 'Ошибка клиента: не передан ключ заказа.',
  idempotency_key_invalid: 'Ошибка клиента: неверный ключ заказа.',
  idempotency_key_reused: 'Повторите заказ ещё раз.',

  ride_not_found: 'Поездка не найдена или недоступна.',
  ride_command_forbidden: 'Это действие недоступно для вашей роли.',
  invalid_ride_transition: 'Статус поездки уже изменился.',
  offer_not_found: 'Предложение больше недоступно.',
  offer_expired: 'Время на ответ истекло.',
  invalid_offer_transition: 'Предложение уже закрыто.',
  invalid_date_range: 'Начало периода позже его конца.',

  ride_not_completed: 'Оплата доступна после завершения поездки.',
  payment_not_found: 'Оплата не найдена.',
  payment_action_forbidden: 'Отметить оплату может только пассажир.',
  invalid_payment_transition: 'Поездка уже оплачена.',
  kaspi_unavailable: 'Оплата через Kaspi сейчас недоступна. Оплатите наличными.',
}

const FALLBACK = 'Что-то пошло не так. Попробуйте ещё раз.'

function retryAfterSuffix(error: ApiError): string {
  const seconds = error.details.retry_after_seconds
  if (typeof seconds !== 'number') return ''
  return ` Повторите через ${Math.ceil(seconds / 60)} мин.`
}

export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK
  const base = MESSAGES[error.code] ?? FALLBACK
  if (error.code === 'too_many_attempts') return base + retryAfterSuffix(error)
  return base
}

export function missingFields(error: unknown): string[] {
  if (!(error instanceof ApiError)) return []
  const fields = error.details.missing_fields
  return Array.isArray(fields) ? fields.filter((f): f is string => typeof f === 'string') : []
}

import { t } from '@/i18n/core'
import { ApiError } from './errors'
const MESSAGES = (): Record<string, string> => ({
  support_not_found: t('Обращение не найдено или недоступно.'),
  support_request_conflict: t('Сообщение изменилось. Попробуйте отправить снова.'),
  support_rate_limited: t('Слишком много сообщений. Немного подождите.'),
  invalid_document: t('Выберите файл в формате PDF.'),
  document_too_large: t('Файл должен быть не больше 10 МБ.'),
  document_version_conflict: t('Обновите карточку: версия документов изменилась.'),
  document_package_locked: t('Для замены создайте новую версию документов.'),
  document_package_incomplete: t('Заполните профиль и загрузите оба документа.'),
  document_package_not_submitted: t('Сначала отправьте документы на проверку.'),
  document_package_not_approved: t('Для выхода на линию нужны проверенные документы.'),
  document_not_found: t('Документ не найден или недоступен.'),
  network_error: t('Нет связи с сервером. Проверьте подключение и попробуйте ещё раз.'),
  unknown_error: t('Сервер ответил неожиданно. Попробуйте ещё раз.'),
  internal_error: t('Внутренняя ошибка сервера. Попробуйте позже.'),
  validation_error: t('Проверьте введённые данные.'),
  not_found: t('Запрошенный ресурс не найден.'),
  method_not_allowed: t('Действие недоступно.'),
  not_authenticated: t('Сессия истекла. Войдите снова.'),
  invalid_credentials: t('Неверный логин или пароль.'),
  too_many_attempts: t('Слишком много попыток входа. Подождите и попробуйте снова.'),
  username_taken: t('Это имя пользователя уже занято.'),
  invalid_google_token: t('Google не подтвердил вход. Попробуйте ещё раз.'),
  google_login_unavailable: t('Вход через Google сейчас недоступен.'),
  csrf_failed: t('Сессия устарела. Обновите страницу.'),
  origin_not_allowed: t('Адрес приложения не разрешён на сервере (CORS_ALLOWED_ORIGINS).'),
  account_blocked: t('Аккаунт заблокирован. Обратитесь к администратору.'),
  user_not_found: t('Пользователь не найден.'),
  admin_account_protected: t('Аккаунт администратора нельзя заблокировать.'),
  account_has_active_ride: t(
    'Сначала завершите активную поездку и подтвердите получение наличных.',
  ),
  forbidden: t('Недостаточно прав для этого действия.'),
  driver_not_found: t('Водитель не найден.'),
  driver_profile_incomplete: t('Профиль водителя заполнен не полностью.'),
  driver_category_not_allowed: t('Выберите хотя бы один тариф, доступный классу вашей машины.'),
  driver_not_approved: t('Водитель ещё не допущен администратором.'),
  driver_on_active_ride: t('Сначала завершите текущую поездку.'),
  driver_busy: t('У вас уже есть активная поездка.'),
  plate_number_taken: t('Этот госномер уже зарегистрирован у другого водителя.'),
  route_points_identical: t('Точки посадки и назначения совпадают.'),
  route_not_found: t('Между выбранными точками нет дорожного маршрута.'),
  routing_unavailable: t('Построение маршрута сейчас недоступно на сервере.'),
  routing_provider_error: t('Сервис маршрутов не ответил. Попробуйте чуть позже.'),
  quote_not_found: t('Расчёт цены не найден. Запросите цену заново.'),
  quote_expired: t('Цена устарела. Запросите новую.'),
  quote_already_used: t('Этот расчёт уже использован. Запросите новую цену.'),
  active_ride_exists: t('У вас уже есть активная поездка.'),
  idempotency_key_required: t('Ошибка клиента: не передан ключ заказа.'),
  idempotency_key_invalid: t('Ошибка клиента: неверный ключ заказа.'),
  idempotency_key_reused: t('Повторите заказ ещё раз.'),
  ride_not_found: t('Поездка не найдена или недоступна.'),
  ride_command_forbidden: t('Это действие недоступно для вашей роли.'),
  invalid_ride_transition: t('Статус поездки уже изменился.'),
  offer_not_found: t('Предложение больше недоступно.'),
  offer_expired: t('Время на ответ истекло.'),
  invalid_offer_transition: t('Предложение уже закрыто.'),
  invalid_date_range: t('Начало периода позже его конца.'),
  ride_not_completed: t('Оплата доступна после завершения поездки.'),
  payment_not_found: t('Оплата не найдена.'),
  payment_action_forbidden: t('Отметить оплату может только пассажир.'),
  invalid_payment_transition: t('Поездка уже оплачена.'),
  kaspi_unavailable: t('Оплата через Kaspi сейчас недоступна. Оплатите наличными.'),
})
const FALLBACK = () => t('Что-то пошло не так. Попробуйте ещё раз.')
function retryAfterSuffix(error: ApiError): string {
  const seconds = error.details.retry_after_seconds
  if (typeof seconds !== 'number') return ''
  return t(' Повторите через {p0} мин.', { p0: Math.ceil(seconds / 60) })
}
export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK()
  const base = MESSAGES()[error.code] ?? FALLBACK()
  if (error.code === 'too_many_attempts') return base + retryAfterSuffix(error)
  return base
}
export function missingFields(error: unknown): string[] {
  if (!(error instanceof ApiError)) return []
  const fields = error.details.missing_fields
  return Array.isArray(fields) ? fields.filter((f): f is string => typeof f === 'string') : []
}

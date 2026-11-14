import { t } from '@/i18n/core'
import type { ApprovalStatus, PaymentMethod, PaymentStatus, RideStatus, UserRole } from '@/api'
export const RIDE_STATUS_LABELS = (): Record<RideStatus, string> => ({
  searching: t('Ищем водителя'),
  assigned: t('Водитель едет к вам'),
  arrived: t('Водитель на месте'),
  in_progress: t('В пути'),
  completed: t('Завершена'),
  cancelled: t('Отменена'),
  no_driver: t('Водитель не найден'),
})
export const PAYMENT_METHOD_LABELS = (): Record<PaymentMethod, string> => ({
  cash: t('Наличные'),
  kaspi_link: 'Kaspi',
})
export const PAYMENT_STATUS_LABELS = (): Record<PaymentStatus, string> => ({
  unpaid: t('Не оплачена'),
  paid: t('Оплачена'),
  refunded: t('Возвращена'),
})
export const APPROVAL_STATUS_LABELS = (): Record<ApprovalStatus, string> => ({
  pending: t('На проверке'),
  approved: t('Одобрен'),
})
export const ROLE_LABELS = (): Record<UserRole, string> => ({
  passenger: t('Пассажир'),
  driver: t('Водитель'),
  admin: t('Администратор'),
})
export const DRIVER_FIELD_LABELS = (): Record<string, string> => ({
  full_name: t('ФИО'),
  phone: t('Телефон'),
  license_number: t('Номер прав'),
  vehicle: t('Автомобиль'),
})

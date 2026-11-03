import type { ApprovalStatus, PaymentMethod, PaymentStatus, RideStatus, UserRole } from '@/api'

export const RIDE_STATUS_LABELS: Record<RideStatus, string> = {
  searching: 'Ищем водителя',
  assigned: 'Водитель едет к вам',
  arrived: 'Водитель на месте',
  in_progress: 'В пути',
  completed: 'Завершена',
  cancelled: 'Отменена',
  no_driver: 'Водитель не найден',
}

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  cash: 'Наличные',
  kaspi_link: 'Kaspi',
}

export const PAYMENT_STATUS_LABELS: Record<PaymentStatus, string> = {
  unpaid: 'Не оплачена',
  paid: 'Оплачена',
  refunded: 'Возвращена',
}

export const APPROVAL_STATUS_LABELS: Record<ApprovalStatus, string> = {
  pending: 'Ожидает допуска',
  approved: 'Допущен',
}

export const ROLE_LABELS: Record<UserRole, string> = {
  passenger: 'Пассажир',
  driver: 'Водитель',
  admin: 'Администратор',
}

export const DRIVER_FIELD_LABELS: Record<string, string> = {
  full_name: 'ФИО',
  phone: 'Телефон',
  license_number: 'Номер прав',
  vehicle: 'Автомобиль',
}

import { Car, ClipboardCheck, History, MapPin, ReceiptText, User, Users } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { UserRole } from '@/api'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
}

export const NAV_ITEMS: Record<UserRole, NavItem[]> = {
  passenger: [
    { to: '/', label: 'Заказ', icon: MapPin, end: true },
    { to: '/history', label: 'Поездки', icon: History },
    { to: '/profile', label: 'Профиль', icon: User },
  ],
  driver: [
    { to: '/driver', label: 'Смена', icon: Car, end: true },
    { to: '/driver/history', label: 'Поездки', icon: History },
    { to: '/driver/profile', label: 'Профиль', icon: User },
  ],
  admin: [
    { to: '/admin', label: 'Допуск', icon: ClipboardCheck, end: true },
    { to: '/admin/rides', label: 'Поездки', icon: ReceiptText },
    { to: '/admin/users', label: 'Пользователи', icon: Users },
  ],
}

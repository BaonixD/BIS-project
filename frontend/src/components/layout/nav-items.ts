import { Car, Clock, List, ShieldCheck, User, Users } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { UserRole } from '@/api'

export interface NavItem {
  to: string
  label: string
  /** Desktop top bar wording when it differs from the bottom nav. */
  topLabel?: string
  icon: LucideIcon
  /** Match only `to` itself, not its sub-paths. */
  end?: boolean
  /** Other path prefixes that belong to this section (e.g. a ride screen under «Такси»). */
  also?: string[]
}

/** Figma «BottomNav» 3:85 — one set per role. */
export const NAV_ITEMS: Record<UserRole, NavItem[]> = {
  passenger: [
    { to: '/', label: 'Такси', icon: Car, end: true, also: ['/ride'] },
    { to: '/history', label: 'История', icon: Clock },
    { to: '/profile', label: 'Профиль', icon: User },
  ],
  driver: [
    { to: '/driver', label: 'Смена', icon: Car, end: true },
    { to: '/driver/history', label: 'История', icon: Clock },
    { to: '/driver/profile', label: 'Профиль', icon: User },
  ],
  admin: [
    { to: '/admin', label: 'Водители', icon: ShieldCheck, end: true },
    { to: '/admin/rides', label: 'Поездки', icon: List },
    { to: '/admin/users', label: 'Люди', topLabel: 'Пользователи', icon: Users },
  ],
}

export const PROFILE_PATH: Partial<Record<UserRole, string>> = {
  passenger: '/profile',
  driver: '/driver/profile',
}

function matchesPrefix(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`)
}

export function isNavItemActive(item: NavItem, pathname: string): boolean {
  if (item.end ? pathname === item.to : matchesPrefix(pathname, item.to)) return true
  return (item.also ?? []).some((prefix) => matchesPrefix(pathname, prefix))
}

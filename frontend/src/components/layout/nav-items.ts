import { t } from '@/i18n/core'
import { Car, Clock, LayoutGrid, List, MessageCircle, ShieldCheck, User, Users } from 'lucide-react'
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
  /** Shows the unread support count next to the label. */
  supportBadge?: boolean
}
/** Figma «BottomNav» 3:85 — one set per role. */
export const NAV_ITEMS = (): Record<UserRole, NavItem[]> => ({
  passenger: [
    { to: '/', label: t('Такси'), icon: Car, end: true, also: ['/ride'] },
    { to: '/history', label: t('История'), icon: Clock },
    { to: '/profile', label: t('Профиль'), icon: User },
  ],
  driver: [
    { to: '/driver', label: t('Смена'), icon: Car, end: true },
    { to: '/driver/history', label: t('История'), icon: Clock },
    { to: '/driver/profile', label: t('Профиль'), icon: User },
  ],
  admin: [
    { to: '/admin/overview', label: t('Обзор'), icon: LayoutGrid },
    { to: '/admin', label: t('Водители'), icon: ShieldCheck, end: true, also: ['/admin/drivers'] },
    { to: '/admin/rides', label: t('Поездки'), icon: List },
    { to: '/admin/users', label: t('Люди'), topLabel: t('Пользователи'), icon: Users },
    { to: '/admin/support', label: t('Поддержка'), icon: MessageCircle, supportBadge: true },
  ],
})
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

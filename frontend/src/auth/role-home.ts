import type { UserRole } from '@/api'

export const ROLE_HOME: Record<UserRole, string> = {
  passenger: '/',
  driver: '/driver',
  admin: '/admin',
}

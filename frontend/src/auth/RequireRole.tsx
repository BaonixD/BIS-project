import { Navigate, Outlet, useLocation } from 'react-router'
import type { UserRole } from '@/api'
import { FullScreenLoader } from '@/components/common/FullScreenLoader'
import { ROLE_HOME } from './role-home'
import { useSession } from './use-session'

export function RequireRole({ roles }: { roles: readonly UserRole[] }) {
  const { status, user } = useSession()
  const location = useLocation()

  if (status === 'loading') return <FullScreenLoader />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (!roles.includes(user.role)) return <Navigate to={ROLE_HOME[user.role]} replace />
  return <Outlet />
}

export function RequireAnonymous() {
  const { status, user } = useSession()
  if (status === 'loading') return <FullScreenLoader />
  if (user) return <Navigate to={ROLE_HOME[user.role]} replace />
  return <Outlet />
}

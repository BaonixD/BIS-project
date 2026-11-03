import type { ComponentType } from 'react'
import { createBrowserRouter, type RouteObject } from 'react-router'
import { RequireAnonymous, RequireRole } from '@/auth/RequireRole'
import { AppShell } from '@/components/layout/AppShell'
import { LoginPage } from '@/pages/auth/LoginPage'
import { RegisterPage } from '@/pages/auth/RegisterPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

/** One chunk per role: a passenger never downloads the driver or admin screens. */
const passenger = () => import('./passenger-pages')
const driver = () => import('./driver-pages')
const admin = () => import('./admin-pages')

function page<M>(load: () => Promise<M>, pick: (module: M) => ComponentType) {
  return async () => ({ Component: pick(await load()) })
}

const devRoutes: RouteObject[] = import.meta.env.DEV
  ? [{ path: '/dev/kit', lazy: page(() => import('@/pages/dev/KitPage'), (m) => m.KitPage) }]
  : []

export const router = createBrowserRouter([
  {
    element: <RequireAnonymous />,
    children: [
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
    ],
  },
  {
    element: <RequireRole roles={['passenger']} />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: '/', lazy: page(passenger, (m) => m.HomePage) },
          { path: '/ride/:rideId', lazy: page(passenger, (m) => m.RidePage) },
          { path: '/history', lazy: page(passenger, (m) => m.HistoryPage) },
          { path: '/profile', lazy: page(passenger, (m) => m.ProfilePage) },
        ],
      },
    ],
  },
  {
    element: <RequireRole roles={['driver']} />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: '/driver', lazy: page(driver, (m) => m.DriverHomePage) },
          { path: '/driver/history', lazy: page(driver, (m) => m.DriverHistoryPage) },
          { path: '/driver/profile', lazy: page(driver, (m) => m.DriverProfilePage) },
        ],
      },
    ],
  },
  {
    element: <RequireRole roles={['admin']} />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: '/admin', lazy: page(admin, (m) => m.AdminDriversPage) },
          { path: '/admin/rides', lazy: page(admin, (m) => m.AdminRidesPage) },
          { path: '/admin/users', lazy: page(admin, (m) => m.AdminUsersPage) },
        ],
      },
    ],
  },
  ...devRoutes,
  { path: '*', element: <NotFoundPage /> },
])

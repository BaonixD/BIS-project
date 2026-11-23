import type { ComponentType } from 'react'
import { createBrowserRouter, type RouteObject } from 'react-router'
import { RequireAnonymous, RequireRole } from '@/auth/RequireRole'
import { FullScreenLoader } from '@/components/common/FullScreenLoader'
import { AppShell } from '@/components/layout/AppShell'
import { LoginPage } from '@/pages/auth/LoginPage'
import { RegisterPage } from '@/pages/auth/RegisterPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

/** One chunk per role: a passenger never downloads the driver or admin screens. */
const passenger = () => import('./passenger-pages')
const driver = () => import('./driver-pages')
const admin = () => import('./admin-pages')
const supportList = () => import('@/pages/support/SupportListPage')
const supportThread = () => import('@/pages/support/SupportThreadPage')
const supportChat = () => import('@/pages/support/SupportChatPage')

function page<M>(load: () => Promise<M>, pick: (module: M) => ComponentType) {
  return {
    lazy: async () => ({ Component: pick(await load()) }),
    HydrateFallback: FullScreenLoader,
  }
}

const devRoutes: RouteObject[] = import.meta.env.DEV
  ? [{ path: '/dev/kit', ...page(() => import('@/pages/dev/KitPage'), (m) => m.KitPage) }]
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
          { path: '/support', ...page(supportChat, (m) => m.SupportChatPage) },
          { path: '/support/:ticketId', ...page(supportChat, (m) => m.SupportChatPage) },
          { path: '/', ...page(passenger, (m) => m.HomePage) },
          { path: '/ride/:rideId', ...page(passenger, (m) => m.RidePage) },
          { path: '/history', ...page(passenger, (m) => m.HistoryPage) },
          { path: '/history/:rideId', ...page(passenger, (m) => m.RideDetailsPage) },
          { path: '/profile', ...page(passenger, (m) => m.ProfilePage) },
          { path: '/profile/settings', ...page(passenger, (m) => m.SettingsPage) },
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
          { path: '/driver/support', ...page(supportChat, (m) => m.SupportChatPage) },
          {
            path: '/driver/support/:ticketId',
            ...page(supportChat, (m) => m.SupportChatPage),
          },
          { path: '/driver', ...page(driver, (m) => m.DriverHomePage) },
          { path: '/driver/history', ...page(driver, (m) => m.DriverHistoryPage) },
          { path: '/driver/profile', ...page(driver, (m) => m.DriverProfilePage) },
          { path: '/driver/documents', ...page(driver, (m) => m.DriverDocumentsPage) },
          { path: '/driver/settings', ...page(driver, (m) => m.DriverSettingsPage) },
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
          { path: '/admin/support', ...page(supportList, (m) => m.SupportListPage) },
          { path: '/admin/support/:ticketId', ...page(supportThread, (m) => m.SupportThreadPage) },
          { path: '/admin', ...page(admin, (m) => m.AdminDriversPage) },
          { path: '/admin/overview', ...page(admin, (m) => m.AdminOverviewPage) },
          { path: '/admin/users/:userId', ...page(admin, (m) => m.AdminUserPage) },
          { path: '/admin/rides/:rideId', ...page(admin, (m) => m.AdminRidePage) },
          { path: '/admin/drivers/:driverId', ...page(admin, (m) => m.AdminDriverPage) },
          { path: '/admin/rides', ...page(admin, (m) => m.AdminRidesPage) },
          { path: '/admin/users', ...page(admin, (m) => m.AdminUsersPage) },
        ],
      },
    ],
  },
  ...devRoutes,
  { path: '*', element: <NotFoundPage /> },
])

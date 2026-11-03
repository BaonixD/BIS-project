import { createBrowserRouter } from 'react-router'
import { RequireAnonymous, RequireRole } from '@/auth/RequireRole'
import { AppShell } from '@/components/layout/AppShell'
import { AdminDriversPage } from '@/pages/admin/AdminDriversPage'
import { AdminRidesPage } from '@/pages/admin/AdminRidesPage'
import { AdminUsersPage } from '@/pages/admin/AdminUsersPage'
import { LoginPage } from '@/pages/auth/LoginPage'
import { RegisterPage } from '@/pages/auth/RegisterPage'
import { DriverHistoryPage } from '@/pages/driver/DriverHistoryPage'
import { DriverHomePage } from '@/pages/driver/DriverHomePage'
import { DriverProfilePage } from '@/pages/driver/DriverProfilePage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { HistoryPage } from '@/pages/passenger/HistoryPage'
import { HomePage } from '@/pages/passenger/HomePage'
import { ProfilePage } from '@/pages/passenger/ProfilePage'
import { RidePage } from '@/pages/passenger/RidePage'

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
          { path: '/', element: <HomePage /> },
          { path: '/ride/:rideId', element: <RidePage /> },
          { path: '/history', element: <HistoryPage /> },
          { path: '/profile', element: <ProfilePage /> },
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
          { path: '/driver', element: <DriverHomePage /> },
          { path: '/driver/history', element: <DriverHistoryPage /> },
          { path: '/driver/profile', element: <DriverProfilePage /> },
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
          { path: '/admin', element: <AdminDriversPage /> },
          { path: '/admin/rides', element: <AdminRidesPage /> },
          { path: '/admin/users', element: <AdminUsersPage /> },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])

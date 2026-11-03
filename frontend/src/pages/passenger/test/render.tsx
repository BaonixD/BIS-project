import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { LocationProbe } from './LocationProbe'


/** Renders passenger routes in a memory router with a fresh query client (no retries). */
export function renderRoutes(routes: { path: string; element: ReactNode }[], path: string, state?: unknown) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const router = createMemoryRouter(
    [...routes.map((route) => ({ ...route, element: <>{route.element}<LocationProbe /></> })), { path: '*', element: <LocationProbe /> }],
    { initialEntries: [{ pathname: path, state }] },
  )
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { queryClient, router }
}

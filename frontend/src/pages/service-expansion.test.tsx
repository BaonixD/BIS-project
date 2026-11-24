import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, expect, it, vi } from 'vitest'
import { DriverDocumentsPage } from './driver/DriverDocumentsPage'
import { SupportChatPage } from './support/SupportChatPage'

const backend = vi.hoisted(() => ({
  calls: [] as { path: string; init?: RequestInit }[],
  pending: false,
}))
vi.mock('@/auth/use-session', () => ({
  useSession: () => ({ user: { id: 'u1', role: 'driver', username: 'driver' } }),
}))
vi.mock('@/api/request', () => ({
  request: async (path: string, init?: RequestInit) => {
    backend.calls.push({ path, init })
    if (path === '/drivers/me/documents/submit') {
      backend.pending = true
      return {}
    }
    if (path === '/drivers/me/documents')
      return {
        package: {
          id: 'package-1',
          version: 3,
          status: backend.pending ? 'pending' : 'draft',
          review_note: null,
          submitted_at: null,
          reviewed_at: null,
        },
        documents: [
          {
            id: 'id',
            kind: 'identity_card',
            filename: 'id.pdf',
            size_bytes: 1000,
            page_count: 1,
            created_at: '2026-11-16T00:00:00Z',
          },
          {
            id: 'license',
            kind: 'driver_license',
            filename: 'license.pdf',
            size_bytes: 1000,
            page_count: 1,
            created_at: '2026-11-16T00:00:00Z',
          },
        ],
        missing_fields: [],
        legacy_exempt: false,
        can_submit: true,
        history: [],
      }
    if (path.startsWith('/support/tickets?')) return { items: [], total: 0, offset: 0, limit: 50 }
    if (path === '/support/assistant') return { available: true }
    if (path === '/support/tickets' && init?.method === 'POST')
      return { id: 'ticket-1', owner_id: 'u1', created_at: '2026-11-23T00:00:00Z' }
    throw new Error(path)
  },
  jsonBody: (body: unknown) => ({
    body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json' },
  }),
}))

beforeEach(() => {
  backend.calls = []
  backend.pending = false
})
function show(element: React.ReactNode, path: string) {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/driver/documents" element={element} />
          <Route path="/driver/support" element={element} />
          <Route path="/driver/support/:ticketId" element={<p>ticket opened</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

it('submits the displayed document version and switches to review state', async () => {
  show(<DriverDocumentsPage />, '/driver/documents')
  expect(await screen.findByText('id.pdf')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Отправить на проверку' }))
  expect(await screen.findByText('На проверке')).toBeInTheDocument()
  const call = backend.calls.find((item) => item.path.endsWith('/submit'))
  expect(JSON.parse(String(call?.init?.body))).toEqual({ package_id: 'package-1', version: 3 })
})

it('starts a ride-linked support chat from the first message and opens it', async () => {
  show(<SupportChatPage />, '/driver/support?ride_id=ride-1')
  await userEvent.type(
    screen.getByRole('textbox', { name: 'Сообщение' }),
    'Please help with this ride',
  )
  await userEvent.click(screen.getByRole('button', { name: 'Отправить' }))
  await waitFor(() => expect(screen.getByText('ticket opened')).toBeInTheDocument())
  const call = backend.calls.find((item) => item.path === '/support/tickets')
  const body = JSON.parse(String(call?.init?.body))
  expect(body.ride_id).toBe('ride-1')
  expect(body.category).toBe('ride')
  expect(body.subject).toBe('Please help with this ride')
  expect(body.body).toBe('Please help with this ride')
  expect(body.client_request_id).toMatch(/^[0-9a-f-]{36}$/)
})

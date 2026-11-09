import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiError, createFakeApi } from '@/test/fake-api'
import { adminDriverFixture, summaryFixture } from '@/test/driver-fixtures'
import { amountCell, paymentCell, rideSubtitle, shortName } from './admin-format'

const fake = vi.hoisted(() => ({
  current: null as ReturnType<typeof import('@/test/fake-api').createFakeApi> | null,
}))

vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>()
  const { createFakeApi: create } = await import('@/test/fake-api')
  fake.current = create()
  return { ...original, api: fake.current.api }
})
const logout = vi.hoisted(() => ({ mutate: vi.fn(), isPending: false }))
vi.mock('@/auth/use-session', () => ({ useSession: () => ({ logout }) }))
vi.mock('@/hooks/use-geocoding', () => ({
  useReverseGeocode: () => ({ data: { title: 'Абая 52' } }),
}))

const { AdminDriversPage } = await import('./AdminDriversPage')
const { AdminDriverPage } = await import('./AdminDriverPage')
const { AdminRidesPage } = await import('./AdminRidesPage')
const { AdminUsersPage } = await import('./AdminUsersPage')
const { AdminUserPage } = await import('./AdminUserPage')
const { AdminOverviewPage } = await import('./AdminOverviewPage')
const api = fake.current as ReturnType<typeof createFakeApi>
const page = (items: unknown[]) => ({ items, limit: 50, offset: 0, total: items.length })

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/admin" element={<AdminDriversPage />} />
          <Route path="/admin/drivers/:driverId" element={<AdminDriverPage />} />
          <Route path="/admin/users" element={<AdminUsersPage />} />
          <Route path="/admin/users/:userId" element={<AdminUserPage />} />
          <Route path="/admin/rides" element={<AdminRidesPage />} />
          <Route path="/admin/overview" element={<AdminOverviewPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => api.reset())

describe('driver approval with the car class', () => {
  it('approves a pending driver as «Комфорт»', async () => {
    const driver = adminDriverFixture({ id: 'd-1' })
    api.on('GET /api/v1/admin/drivers', () => page([driver]))
    api.on('POST /api/v1/admin/drivers/{driver_id}/approve', () => ({
      ...driver,
      approval_status: 'approved',
    }))
    renderAt('/admin')
    expect(await screen.findByText('1 ждут')).toBeInTheDocument()
    expect(screen.getByText('Toyota Camry · белый · 123 ABC 02')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Одобрить' }))
    const dialog = screen.getByRole('dialog', { name: 'Класс машины' })
    await userEvent.click(within(dialog).getByRole('radio', { name: /Комфорт$/ }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Одобрить' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    const call = api.calls.find((item) => item.path.endsWith('/approve'))
    expect(call?.init).toEqual({
      params: { path: { driver_id: 'd-1' } },
      body: { car_class: 'comfort' },
    })
  })

  it('changes the class of an approved driver with PATCH from the driver card', async () => {
    const driver = adminDriverFixture({ id: 'd-2', approval_status: 'approved' })
    api.on('GET /api/v1/admin/drivers/{driver_id}', () => driver)
    api.on('PATCH /api/v1/admin/drivers/{driver_id}', () => driver)
    renderAt('/admin/drivers/d-2')
    expect(await screen.findByText('Все обязательные поля заполнены')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Сменить класс машины' }))
    await userEvent.click(screen.getByRole('radio', { name: /Бизнес$/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Сохранить класс' }))
    await waitFor(() => expect(api.calls.some((item) => item.method === 'PATCH')).toBe(true))
    expect(api.calls.find((item) => item.method === 'PATCH')?.init.body).toEqual({
      car_class: 'business',
    })
  })

  it('keeps the sheet open and names the missing fields when the profile is incomplete', async () => {
    const driver = adminDriverFixture({ id: 'd-3', missing_fields: ['vehicle'] })
    api.on('GET /api/v1/admin/drivers/{driver_id}', () => driver)
    api.on('POST /api/v1/admin/drivers/{driver_id}/approve', () =>
      apiError(409, 'driver_profile_incomplete'),
    )
    renderAt('/admin/drivers/d-3')
    expect(await screen.findByText('Не заполнено: Автомобиль')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Одобрить водителя' }))
    await userEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Одобрить' }),
    )
    await waitFor(() => expect(api.calls.some((item) => item.path.endsWith('/approve'))).toBe(true))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })
})

describe('admin logout on mobile', () => {
  it.each([
    ['drivers', AdminDriversPage],
    ['rides', AdminRidesPage],
    ['people', AdminUsersPage],
  ])('the %s page has a logout button', async (_name, Page) => {
    logout.mutate.mockClear()
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <Page />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Выйти' }))
    expect(logout.mutate).toHaveBeenCalledOnce()
  })
})

describe('admin ride rows', () => {
  it('formats names, money and payment like Figma 6:534 and 7:111', () => {
    expect(shortName('Арман Нурланов')).toBe('Арман Н.')
    expect(shortName('Дана')).toBe('Дана')
    const searching = summaryFixture({
      status: 'searching',
      driver_id: null,
      payment_status: 'unpaid',
    })
    expect(rideSubtitle(searching, 'Дана', null)).toBe('Дана · ищем водителя')
    expect(rideSubtitle(summaryFixture({ status: 'cancelled' }), 'Мадина', null)).toBe('Мадина · —')
    expect(paymentCell(searching)).toBe('—')
    expect(paymentCell(summaryFixture())).toBe('Kaspi · оплачено')
    expect(
      paymentCell(
        summaryFixture({ status: 'in_progress', payment_method: 'cash', payment_status: 'unpaid' }),
      ),
    ).toBe('Наличные')
    expect(amountCell(summaryFixture({ status: 'cancelled' }))).toBe('—')
  })
})

describe('admin management workflows', () => {
  it('searches the whole user collection and resets pagination when a filter changes', async () => {
    api.on('GET /api/v1/admin/users', () => ({ ...page([]), total: 65 }))
    renderAt('/admin/users?offset=20&role=driver')
    await screen.findByText('21–40 из 65')
    await userEvent.type(
      screen.getByRole('textbox', { name: 'Поиск по имени, логину или телефону' }),
      'Айгерим',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Найти' }))
    await waitFor(() =>
      expect(api.calls.at(-1)?.init.params?.query).toMatchObject({
        q: 'Айгерим',
        role: 'driver',
        offset: 0,
        limit: 20,
      }),
    )
    await userEvent.click(screen.getByRole('button', { name: /Вперёд/ }))
    await waitFor(() =>
      expect(api.calls.at(-1)?.init.params?.query).toMatchObject({ q: 'Айгерим', offset: 20 }),
    )
  })

  it('requires confirmation and a reason, then keeps a rejected block open with its error', async () => {
    const user = {
      id: 'u-1',
      username: 'aigerim',
      role: 'passenger',
      display_name: 'Айгерим',
      created_at: '2026-11-03T09:00:00Z',
      blocked_at: null,
      block_reason: null,
    }
    api.on('GET /api/v1/admin/users/{user_id}', () => user)
    api.on('PUT /api/v1/admin/users/{user_id}/access', () =>
      apiError(409, 'account_has_active_ride'),
    )
    renderAt('/admin/users/u-1')
    await userEvent.click(await screen.findByRole('button', { name: 'Заблокировать аккаунт' }))
    const dialog = screen.getByRole('dialog')
    expect(api.calls.some((call) => call.method === 'PUT')).toBe(false)
    expect(within(dialog).getByRole('button', { name: 'Подтвердить блокировку' })).toBeDisabled()
    await userEvent.type(
      within(dialog).getByRole('textbox', { name: 'Причина блокировки' }),
      'Проверка жалобы',
    )
    await userEvent.click(within(dialog).getByRole('button', { name: 'Подтвердить блокировку' }))
    expect(
      await within(dialog).findByText(
        'Сначала завершите активную поездку и подтвердите получение наличных.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(api.calls.find((call) => call.method === 'PUT')?.init.body).toEqual({
      blocked: true,
      reason: 'Проверка жалобы',
    })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Отмена' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('restores ride filters from the URL and opens a specific ride', async () => {
    const ride = {
      ...summaryFixture({ status: 'cancelled', payment_status: 'refunded' }),
      passenger_name: 'Айгерим',
      driver_name: 'Арман',
    }
    api.on('GET /api/v1/admin/rides', () => page([ride]))
    renderAt('/admin/rides?view=cancelled&payment_status=refunded&tariff=comfort')
    await screen.findByRole('table')
    expect(
      api.calls.find((call) => call.path === '/api/v1/admin/rides')?.init.params?.query,
    ).toMatchObject({
      status: ['cancelled', 'no_driver'],
      payment_status: 'refunded',
      tariff: 'comfort',
    })
    const table = screen.getByRole('table')
    expect(within(table).getByText('Kaspi · возврат')).toBeInTheDocument()
    expect(within(table).getByRole('link', { name: 'Айгерим' })).toHaveAttribute(
      'href',
      '/admin/users/passenger-1',
    )
    expect(within(table).getByRole('link', { name: /Абая/ })).toHaveAttribute(
      'href',
      '/admin/rides/ride-s',
    )
  })

  it('shows service-wide totals and links to the corresponding lists', async () => {
    api.on('GET /api/v1/admin/overview', () => ({
      total_users: 543,
      blocked_users: 2,
      pending_drivers: 12,
      online_drivers: 7,
      active_rides: 3,
      completed_rides: 101,
      cancelled_rides: 5,
      collected_kzt: 290000,
      outstanding_cash_kzt: 4500,
    }))
    renderAt('/admin/overview')
    expect(await screen.findByText('543')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Ждут проверки/ })).toHaveAttribute(
      'href',
      '/admin?status=pending',
    )
    expect(screen.getByRole('link', { name: /Ожидают наличных/ })).toHaveAttribute(
      'href',
      '/admin/rides?view=completed&payment_status=unpaid&payment_method=cash',
    )
  })
})

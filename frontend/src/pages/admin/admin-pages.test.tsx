import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiError, createFakeApi } from '@/test/fake-api'
import { adminDriverFixture, summaryFixture } from '@/test/driver-fixtures'
import { amountCell, paymentCell, rideSubtitle, shortName } from './admin-format'

const fake = vi.hoisted(() => ({ current: null as ReturnType<typeof import('@/test/fake-api').createFakeApi> | null }))

vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>()
  const { createFakeApi: create } = await import('@/test/fake-api')
  fake.current = create()
  return { ...original, api: fake.current.api }
})
vi.mock('@/hooks/use-geocoding', () => ({ useReverseGeocode: () => ({ data: { title: 'Абая 52' } }) }))

const { AdminDriversPage } = await import('./AdminDriversPage')
const { AdminDriverPage } = await import('./AdminDriverPage')
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
    api.on('POST /api/v1/admin/drivers/{driver_id}/approve', () => ({ ...driver, approval_status: 'approved' }))
    renderAt('/admin')
    expect(await screen.findByText('1 ждут')).toBeInTheDocument()
    expect(screen.getByText('Toyota Camry · белый · 123 ABC 02')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Одобрить' }))
    const dialog = screen.getByRole('dialog', { name: 'Класс машины' })
    await userEvent.click(within(dialog).getByRole('radio', { name: /Комфорт$/ }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Одобрить' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    const call = api.calls.find((item) => item.path.endsWith('/approve'))
    expect(call?.init).toEqual({ params: { path: { driver_id: 'd-1' } }, body: { car_class: 'comfort' } })
  })

  it('changes the class of an approved driver with PATCH from the driver card', async () => {
    const driver = adminDriverFixture({ id: 'd-2', approval_status: 'approved' })
    api.on('GET /api/v1/admin/drivers', () => page([driver]))
    api.on('PATCH /api/v1/admin/drivers/{driver_id}', () => driver)
    renderAt('/admin/drivers/d-2')
    expect(await screen.findByText('Все обязательные поля заполнены')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Сменить класс машины' }))
    await userEvent.click(screen.getByRole('radio', { name: /Бизнес$/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Сохранить класс' }))
    await waitFor(() => expect(api.calls.some((item) => item.method === 'PATCH')).toBe(true))
    expect(api.calls.find((item) => item.method === 'PATCH')?.init.body).toEqual({ car_class: 'business' })
  })

  it('keeps the sheet open and names the missing fields when the profile is incomplete', async () => {
    const driver = adminDriverFixture({ id: 'd-3', missing_fields: ['vehicle'] })
    api.on('GET /api/v1/admin/drivers', () => page([driver]))
    api.on('POST /api/v1/admin/drivers/{driver_id}/approve', () => apiError(409, 'driver_profile_incomplete'))
    renderAt('/admin/drivers/d-3')
    expect(await screen.findByText('Не заполнено: Автомобиль')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Одобрить водителя' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Одобрить' }))
    await waitFor(() => expect(api.calls.some((item) => item.path.endsWith('/approve'))).toBe(true))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })
})

describe('admin ride rows', () => {
  it('formats names, money and payment like Figma 6:534 and 7:111', () => {
    expect(shortName('Арман Нурланов')).toBe('Арман Н.')
    expect(shortName('Дана')).toBe('Дана')
    const searching = summaryFixture({ status: 'searching', driver_id: null, payment_status: 'unpaid' })
    expect(rideSubtitle(searching, 'Дана', null)).toBe('Дана · ищем водителя')
    expect(rideSubtitle(summaryFixture({ status: 'cancelled' }), 'Мадина', null)).toBe('Мадина · —')
    expect(paymentCell(searching)).toBe('—')
    expect(paymentCell(summaryFixture())).toBe('Kaspi · оплачено')
    expect(paymentCell(summaryFixture({ status: 'in_progress', payment_method: 'cash', payment_status: 'unpaid' }))).toBe(
      'Наличные',
    )
    expect(amountCell(summaryFixture({ status: 'cancelled' }))).toBe('—')
  })
})

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiError, createFakeApi, memoryStorage } from '@/test/fake-api'
import { driverFixture, offerFixture, rideFixture } from '@/test/driver-fixtures'

const fake = vi.hoisted(() => ({ current: null as ReturnType<typeof import('@/test/fake-api').createFakeApi> | null }))

vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>()
  const { createFakeApi: create } = await import('@/test/fake-api')
  fake.current = create()
  return { ...original, api: fake.current.api }
})
vi.mock('@/components/map/MapView', () => ({ MapView: () => <div data-testid="map" /> }))
vi.mock('@/hooks/use-geocoding', () => ({
  useReverseGeocode: (point: unknown) => ({ data: point ? { title: 'ул. Абая, 52' } : undefined }),
}))

const { DriverHomePage } = await import('./DriverHomePage')
const api = fake.current as ReturnType<typeof createFakeApi>
const page = (items: unknown[]) => ({ items, limit: 20, offset: 0, total: items.length })

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <DriverHomePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

vi.stubGlobal('localStorage', memoryStorage())

beforeEach(() => {
  api.reset()
  localStorage.clear()
  api.on('GET /api/v1/rides', () => page([]))
})

afterEach(() => vi.useRealTimers())

describe('DriverHomePage', () => {
  it('shows the review banner and a disabled go-online button to a pending driver', async () => {
    api.on('GET /api/v1/drivers/me', () => driverFixture({ approval_status: 'pending', missing_fields: ['vehicle'] }))
    renderPage()
    expect(await screen.findByText('Аккаунт на проверке')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Выйти на линию' })).toBeDisabled()
    expect(screen.getByText('Профиль заполнен')).toBeInTheDocument()
    expect(screen.getByText('Добавьте машину')).toBeInTheDocument()
  })

  it('goes online from the offline screen', async () => {
    api.on('GET /api/v1/drivers/me', () => driverFixture())
    api.on('PUT /api/v1/drivers/me/availability', () => driverFixture({ online: true }))
    api.on('GET /api/v1/drivers/me/offers', () => page([]))
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Выйти на линию' }))
    expect(await screen.findByText('Ищем заказы рядом')).toBeInTheDocument()
    expect(api.calls.find((call) => call.method === 'PUT' && call.path.endsWith('/availability'))?.init.body).toEqual({
      online: true,
    })
  })

  it('counts the offer down from expires_at and accepts it into the ride screen', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date('2026-11-03T09:00:06Z') })
    api.on('GET /api/v1/drivers/me', () => driverFixture({ online: true }))
    api.on('GET /api/v1/drivers/me/offers', () => page([offerFixture()]))
    api.on('POST /api/v1/ride-offers/{offer_id}/accept', () => rideFixture())
    api.on('GET /api/v1/rides/{ride_id}', () => rideFixture())
    renderPage()
    expect(await screen.findByRole('timer')).toHaveAccessibleName('Осталось 24 с')
    await act(() => vi.advanceTimersByTimeAsync(4000))
    expect(screen.getByRole('timer')).toHaveAccessibleName('Осталось 20 с')

    await userEvent.click(screen.getByRole('button', { name: 'Принять' }))
    expect(await screen.findByText('Едьте к пассажиру')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Я на месте' })).toBeInTheDocument()
    expect(localStorage.getItem('bis.driver.rideId')).toBe('ride-1')
  })

  it('disables the answer buttons once the offer has expired', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date('2026-11-03T09:00:31Z') })
    api.on('GET /api/v1/drivers/me', () => driverFixture({ online: true }))
    api.on('GET /api/v1/drivers/me/offers', () => page([offerFixture()]))
    renderPage()
    expect(await screen.findByRole('timer')).toHaveAccessibleName('Осталось 0 с')
    expect(screen.getByRole('button', { name: 'Принять' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Отклонить' })).toBeDisabled()
  })

  it('releases the order with the reason and the comment', async () => {
    localStorage.setItem('bis.driver.rideId', 'ride-1')
    api.on('GET /api/v1/drivers/me', () => driverFixture({ online: true }))
    api.on('GET /api/v1/rides/{ride_id}', () => rideFixture({ status: 'arrived', arrived_at: '2026-11-03T09:05:00Z' }))
    api.on('POST /api/v1/rides/{ride_id}/release', () => rideFixture({ status: 'searching', driver_id: null }))
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Отказаться от заказа' }))
    const submit = screen.getByRole('button', { name: 'Отказаться' })
    expect(submit).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Пассажир не вышел' }))
    await userEvent.type(screen.getByLabelText('Комментарий'), 'ждал 10 минут')
    api.on('GET /api/v1/rides/{ride_id}', () => apiError(404, 'ride_not_found'))
    await userEvent.click(submit)
    await waitFor(() => expect(localStorage.getItem('bis.driver.rideId')).toBeNull())
    expect(api.calls.find((call) => call.path.endsWith('/release'))?.init.body).toEqual({
      reason: 'Пассажир не вышел: ждал 10 минут',
    })
  })

  it('tells the driver the passenger cancelled and forgets the ride on «Понятно»', async () => {
    localStorage.setItem('bis.driver.rideId', 'ride-1')
    api.on('GET /api/v1/drivers/me', () => driverFixture({ online: true }))
    api.on('GET /api/v1/drivers/me/offers', () => page([]))
    api.on('GET /api/v1/rides/{ride_id}', () => rideFixture({ status: 'cancelled' }))
    renderPage()
    expect(await screen.findByText('Пассажир отменил поездку')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Понятно' }))
    expect(await screen.findByText('Ищем заказы рядом')).toBeInTheDocument()
    expect(localStorage.getItem('bis.driver.rideId')).toBeNull()
  })

  it('asks for cash, confirms it and rates the passenger', async () => {
    localStorage.setItem('bis.driver.rideId', 'ride-1')
    const ride = rideFixture({ status: 'completed', completed_at: '2026-11-03T09:30:00Z' })
    api.on('GET /api/v1/drivers/me', () => driverFixture({ online: true }))
    api.on('GET /api/v1/drivers/me/offers', () => page([]))
    api.on('GET /api/v1/rides/{ride_id}', () => ride)
    api.on('GET /api/v1/rides/{ride_id}/payment', () => ({ ride_id: 'ride-1', method: 'cash', status: 'unpaid' }))
    api.on('POST /api/v1/rides/{ride_id}/payment/cash-received', () => ({ ride_id: 'ride-1', method: 'cash', status: 'paid' }))
    api.on('POST /api/v1/rides/{ride_id}/rating', () => apiError(409, 'rating_already_exists'))
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Наличные получены' }))
    expect(await screen.findByText('Получено наличными')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('radio', { name: '4 из 5' }))
    await userEvent.click(screen.getByRole('button', { name: 'Вежливый' }))
    await userEvent.click(screen.getByRole('button', { name: 'Оценить и к новым заказам' }))
    expect(await screen.findByText('Ищем заказы рядом')).toBeInTheDocument()
    expect(api.calls.find((call) => call.path.endsWith('/rating'))?.init.body).toEqual({
      stars: 4,
      tags: ['polite'],
      comment: null,
    })
  })
})

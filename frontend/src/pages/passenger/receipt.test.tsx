import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setLocale } from '@/i18n/core'
import { Achievements } from '@/components/common/Achievements'
import { DRIVER, makeRide } from './test/fixtures'
import { renderRoutes } from './test/render'
import { ReceiptPage } from './ReceiptPage'
import { RidePage } from './RidePage'
import { receiptNumber } from './model/receipt'

const server = await vi.hoisted(async () => (await import('./test/fake-server')).installFakeFetch())

vi.mock('@/auth/use-session', () => ({
  useSession: () => ({
    user: { id: 'p1', role: 'passenger', username: 'passenger' },
  }),
}))
vi.mock('@/components/map/MapView', () => ({
  MapView: () => <div data-testid="map" />,
}))

const PAID_AT = '2026-11-03T09:00:00Z'

function payment(overrides: Record<string, unknown> = {}) {
  return {
    ride_id: 'ride-1',
    amount_kzt: 2000,
    currency: 'KZT',
    method: 'kaspi_link',
    status: 'paid',
    paid_at: PAID_AT,
    refunded_at: null,
    payment_url: 'https://pay.kaspi.kz/pay/test',
    ...overrides,
  }
}

const routes = [
  { path: '/ride/:rideId', element: <RidePage /> },
  { path: '/history/:rideId/receipt', element: <ReceiptPage /> },
]

beforeEach(async () => {
  const { memoryStorage } = await import('./test/fake-server')
  vi.stubGlobal('localStorage', memoryStorage())
  vi.stubGlobal('sessionStorage', memoryStorage())
  server.routes.clear()
  server.calls.length = 0
  server.routes.set('GET /api/v1/rides/ride-1/payment', () => payment())
})

afterEach(() => {
  act(() => setLocale('ru'))
  vi.unstubAllGlobals()
})

describe('Kaspi receipt', () => {
  it('numbers a receipt from the ride id', () => {
    expect(receiptNumber('3f9a12bc-77de-4e0a-9d11-0c2b9f0e4a51')).toBe('TT-3F9A12BC')
  })

  it('prints the receipt as soon as Kaspi is charged and opens the full one', async () => {
    server.routes.set('GET /api/v1/rides/ride-1', () =>
      makeRide({ status: 'assigned', payment_status: 'paid', driver: DRIVER }),
    )
    const { router } = renderRoutes(routes, '/ride/ride-1')
    const slip = await screen.findByRole('region', { name: 'Чек об оплате' })
    expect(within(slip).getByText('TT-RIDE1')).toBeInTheDocument()
    expect(within(slip).getByText('Оплачено')).toBeInTheDocument()
    expect(within(slip).getByText('Kaspi')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Открыть чек' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/history/ride-1/receipt'))
  })

  it('shows the full receipt with bonuses and shares its text', async () => {
    const share = vi.fn(async () => {})
    vi.stubGlobal('navigator', { ...navigator, share })
    server.routes.set('GET /api/v1/rides/ride-1', () =>
      makeRide({
        status: 'completed',
        payment_status: 'paid',
        bonus_kzt: 200,
        driver: DRIVER,
      }),
    )
    renderRoutes(routes, '/history/ride-1/receipt')
    const slip = await screen.findByRole('region', { name: 'Чек об оплате' })
    expect(await within(slip).findByText('2 000 ₸')).toBeInTheDocument()
    expect(within(slip).getByText('−200 ₸')).toBeInTheDocument()
    expect(within(slip).getByText('2 200 ₸')).toBeInTheDocument()
    expect(within(slip).getByText(/Учебная оплата/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Поделиться' }))
    expect(share).toHaveBeenCalledWith(
      expect.objectContaining({ text: expect.stringContaining('TT-RIDE1') }),
    )
  })

  it('marks a refunded Kaspi payment on the receipt', async () => {
    server.routes.set('GET /api/v1/rides/ride-1/payment', () =>
      payment({ status: 'refunded', refunded_at: PAID_AT }),
    )
    server.routes.set('GET /api/v1/rides/ride-1', () =>
      makeRide({ status: 'cancelled', payment_status: 'refunded' }),
    )
    renderRoutes(routes, '/history/ride-1/receipt')
    const slip = await screen.findByRole('region', { name: 'Чек об оплате' })
    expect(await within(slip).findByText('Возвращено')).toBeInTheDocument()
  })

  it('links the receipt from the finished Kaspi ride', async () => {
    server.routes.set('GET /api/v1/rides/ride-1', () =>
      makeRide({ status: 'completed', payment_status: 'paid' }),
    )
    const { router } = renderRoutes(routes, '/ride/ride-1')
    await userEvent.click(await screen.findByRole('button', { name: 'Чек' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/history/ride-1/receipt'))
  })
})

describe('Progress', () => {
  it('shows the level, XP, the weekly streak and the weekly quest', async () => {
    server.routes.set('GET /api/v1/users/me/achievements', () => ({
      completed_rides: 6,
      xp: 1170,
      level: { number: 3, level_start_xp: 800, next_level_xp: 1500 },
      streak: { current_weeks: 3, best_weeks: 3, active_this_week: true },
      weekly_quest: {
        code: 'weekly_rides',
        current: 2,
        target: 3,
        completed: false,
        reward_xp: 150,
        ends_at: new Date(Date.now() + 86_400_000).toISOString(),
      },
      achievements: [
        { code: 'first_ride', current: 6, target: 1, unlocked: true, xp: 50 },
        { code: 'night_owl', current: 0, target: 1, unlocked: false, xp: 50 },
      ],
    }))
    renderRoutes([{ path: '/', element: <Achievements /> }], '/')
    expect(await screen.findByText('Путешественник')).toBeInTheDocument()
    expect(screen.getByText('Уровень 3')).toBeInTheDocument()
    expect(screen.getByText('1 170 XP')).toBeInTheDocument()
    expect(screen.getByText('330 XP до уровня 4')).toBeInTheDocument()
    expect(screen.getByText('3 нед. подряд')).toBeInTheDocument()
    expect(screen.getByText('2 из 3 поездок')).toBeInTheDocument()
    expect(screen.getByText('+150 XP')).toBeInTheDocument()
    expect(screen.getByText('Ночная птица')).toBeInTheDocument()
    expect(screen.getByText('Открыто 1 из 2')).toBeInTheDocument()
  })
})

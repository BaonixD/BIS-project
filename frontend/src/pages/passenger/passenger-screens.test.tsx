import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { RideDetails } from '@/api'
import { DRIVER, makeRide, QUOTE } from './test/fixtures'
import { renderRoutes } from './test/render'
import { HomePage } from './HomePage'
import { RidePage } from './RidePage'

const server = await vi.hoisted(async () => (await import('./test/fake-server')).installFakeFetch())

vi.mock('@/components/map/MapView', () => ({ MapView: () => <div data-testid="map" /> }))

beforeEach(async () => {
  const { memoryStorage } = await import('./test/fake-server')
  vi.stubGlobal('localStorage', memoryStorage())
  vi.stubGlobal('sessionStorage', memoryStorage())
  server.routes.clear()
  server.calls.length = 0
  server.routes.set('GET /api/v1/rides', () => ({ items: [], limit: 1, offset: 0, total: 0 }))
})

afterEach(() => vi.unstubAllGlobals())

function serveRide(ride: RideDetails | (() => RideDetails)) {
  server.routes.set(`GET /api/v1/rides/ride-1`, () => (typeof ride === 'function' ? ride() : ride))
}

const rideRoutes = [
  { path: '/ride/:rideId', element: <RidePage /> },
  { path: '/', element: <p>home</p> },
]

describe('RidePage picks the screen from the ride status', () => {
  it.each([
    [makeRide(), 'Подбираем ближайшего водителя'],
    [makeRide({ status: 'assigned', payment_method: 'cash', driver: DRIVER }), 'Приедет через ~4 мин'],
    [makeRide({ status: 'arrived', driver: DRIVER, arrived_at: new Date().toISOString() }), 'Выходите — вас ждут'],
    [makeRide({ status: 'in_progress', driver: DRIVER, started_at: new Date().toISOString() }), /Прибытие ~/],
    [makeRide({ status: 'completed', payment_method: 'cash', payment_status: 'unpaid' }), 'Оплатите наличными'],
    [makeRide({ status: 'completed', payment_status: 'paid' }), 'Поездка завершена'],
    [makeRide({ status: 'cancelled', payment_status: 'refunded' }), 'Поездка отменена'],
    [makeRide({ status: 'no_driver' }), 'Свободных водителей нет'],
  ] as const)('%#: %s', async (ride, heading) => {
    serveRide(ride)
    renderRoutes(rideRoutes, '/ride/ride-1')
    expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument()
  })

  it('shows «Водитель найден» once for a paid Kaspi ride, then tracking', async () => {
    serveRide(makeRide({ status: 'assigned', payment_status: 'paid', driver: DRIVER }))
    renderRoutes(rideRoutes, '/ride/ride-1')
    expect(await screen.findByRole('heading', { name: 'Водитель найден' })).toBeInTheDocument()
    expect(screen.getByText(/2 200 ₸ списано через Kaspi/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Где мой водитель?' }))
    expect(await screen.findByRole('heading', { name: 'Приедет через ~4 мин' })).toBeInTheDocument()
    expect(sessionStorage.getItem('bis.driverFoundSeen:ride-1')).toBe('1')
  })

  it('tells about a driver who declined when the ride is searching again', async () => {
    let ride = makeRide({ status: 'assigned', payment_method: 'cash', driver: DRIVER })
    serveRide(() => ride)
    const { queryClient } = renderRoutes(rideRoutes, '/ride/ride-1')
    await screen.findByRole('heading', { name: 'Приедет через ~4 мин' })
    ride = makeRide({ payment_method: 'cash' })
    await queryClient.invalidateQueries()
    expect(await screen.findByRole('heading', { name: 'Подбираем другого водителя' })).toBeInTheDocument()
  })

  it('asks before cancelling and promises the Kaspi refund', async () => {
    sessionStorage.setItem('bis.driverFoundSeen:ride-1', '1')
    serveRide(makeRide({ status: 'assigned', payment_status: 'paid', driver: DRIVER }))
    server.routes.set('POST /api/v1/rides/ride-1/cancel', () => makeRide({ status: 'cancelled' }))
    renderRoutes(rideRoutes, '/ride/ride-1')
    await userEvent.click(await screen.findByRole('button', { name: 'Отменить' }))
    expect(screen.getByRole('heading', { name: 'Отменить поездку?' })).toBeInTheDocument()
    expect(screen.getByText('Водитель уже едет к вам. Оплата Kaspi 2 200 ₸ вернётся автоматически.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Да, отменить' }))
    await waitFor(() => expect(server.calls.some((call) => call.path === '/api/v1/rides/ride-1/cancel')).toBe(true))
  })

  it('sends the rating: stars, tags and the comment', async () => {
    serveRide(makeRide({ status: 'completed', payment_status: 'paid' }))
    server.routes.set('POST /api/v1/rides/ride-1/rating', () => ({ stars: 4 }))
    renderRoutes(rideRoutes, '/ride/ride-1')
    await screen.findByRole('heading', { name: 'Поездка завершена' })
    const submit = screen.getByRole('button', { name: 'Отправить оценку' })
    expect(submit).toBeDisabled()
    await userEvent.click(screen.getByRole('radio', { name: '4 из 5' }))
    await userEvent.click(screen.getByRole('button', { name: 'Вежливый' }))
    await userEvent.click(screen.getByRole('button', { name: 'Чисто' }))
    await userEvent.click(screen.getByRole('button', { name: '+ Комментарий' }))
    await userEvent.type(screen.getByRole('textbox', { name: 'Комментарий' }), 'Спасибо')
    await userEvent.click(submit)
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(/^\/$/))
    const call = server.calls.find((c) => c.path === '/api/v1/rides/ride-1/rating')
    expect(call?.body).toEqual({ stars: 4, tags: ['polite', 'clean_car'], comment: 'Спасибо' })
  })
})

describe('HomePage and the active ride', () => {
  it('stays home after a finished ride instead of following the cached active ride back', async () => {
    let active = [makeRide({ status: 'in_progress', driver: DRIVER })]
    server.routes.set('GET /api/v1/rides', () => ({ items: active, limit: 1, offset: 0, total: active.length }))
    serveRide(makeRide({ status: 'completed', payment_status: 'paid', driver: DRIVER }))
    renderRoutes([{ path: '/', element: <HomePage /> }, rideRoutes[0]!], '/')
    expect(await screen.findByRole('heading', { name: 'Поездка завершена' })).toBeInTheDocument()

    active = []
    await userEvent.click(screen.getByRole('button', { name: 'Пропустить' }))

    expect(await screen.findByRole('heading', { name: 'Куда едем?' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(/^\/$/))
  })
})

describe('HomePage orders a ride', () => {
  it('quotes the route, offers four tariffs and orders with the chosen tariff and Kaspi', async () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    server.routes.set('POST /api/v1/rides/quotes', () => QUOTE)
    server.routes.set('POST /api/v1/rides', () => {
      expect(open).toHaveBeenCalledWith('https://pay.kaspi.kz/pay/test', '_blank', 'noopener,noreferrer')
      return makeRide()
    })
    renderRoutes([{ path: '/', element: <HomePage /> }], '/')

    await userEvent.click(await screen.findByRole('button', { name: /Esentai Mall/ }))
    const tariffs = await screen.findByRole('radiogroup', { name: 'Тариф' })
    expect(within(tariffs).getAllByRole('radio').map((radio) => radio.textContent)).toEqual([
      '2 200 ₸Эконом',
      '2 925 ₸Комфорт',
      '3 650 ₸Комфорт+',
      '4 800 ₸Бизнес',
    ])
    await userEvent.click(within(tariffs).getByRole('radio', { name: /Комфорт\+/ }))
    await userEvent.click(screen.getByRole('radio', { name: /Kaspi/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Заказать Комфорт+ · Kaspi' }))

    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/ride/ride-1'))
    const order = server.calls.find((call) => call.method === 'POST' && call.path === '/api/v1/rides')
    expect(order?.body).toEqual({ quote_id: 'quote-1', payment_method: 'kaspi_link', tariff: 'comfort_plus' })
  })

  it('does not open Kaspi for cash', async () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    server.routes.set('POST /api/v1/rides/quotes', () => QUOTE)
    server.routes.set('POST /api/v1/rides', () => makeRide())
    renderRoutes([{ path: '/', element: <HomePage /> }], '/')
    await userEvent.click(await screen.findByRole('button', { name: /Esentai Mall/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Заказать Эконом · Наличные' }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/ride/ride-1'))
    expect(open).not.toHaveBeenCalled()
  })

  it('shows the route error with a retry', async () => {
    server.routes.set('POST /api/v1/rides/quotes', () =>
      new Response(JSON.stringify({ error: { code: 'routing_unavailable', message: 'x', details: {} } }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    renderRoutes([{ path: '/', element: <HomePage /> }], '/')
    await userEvent.click(await screen.findByRole('button', { name: /Esentai Mall/ }))
    expect(await screen.findByRole('heading', { name: 'Не удалось построить маршрут' })).toBeInTheDocument()
    server.routes.set('POST /api/v1/rides/quotes', () => QUOTE)
    await userEvent.click(screen.getByRole('button', { name: 'Повторить' }))
    expect(await screen.findByRole('button', { name: 'Заказать Эконом · Наличные' })).toBeInTheDocument()
  })
})

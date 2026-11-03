import { describe, expect, it, vi } from 'vitest'
import { routeErrorText } from './errors'
import {
  elapsedShare,
  formatClock,
  formatCountdown,
  formatKm,
  formatKmCompact,
  formatMinutes,
  formatPrice,
  formatRideDate,
  historyDayLabel,
  initials,
  pickupEtaMinutes,
  shortName,
  withName,
} from './format'
import { filterStatuses, groupByDay, historyMeta, historyPrice, ridePill } from './history'
import { buildRideOrder, openKaspiLink, orderButtonLabel, tariffOptions } from './order'
import { POPULAR_PLACES, readRecentPlaces, rememberPlace, suggestedPlaces } from './places'
import { buildRating, toggleTag } from './rating'
import { needsPolling, rideScreen, wasReleased } from './ride-screen'
import { ApiError } from '@/api'

const kaspi = { payment_method: 'kaspi_link', payment_status: 'paid' } as const
const cash = { payment_method: 'cash', payment_status: 'unpaid' } as const

describe('rideScreen', () => {
  it.each([
    ['searching', cash, false, 'searching'],
    ['assigned', kaspi, false, 'driver_found'],
    ['assigned', kaspi, true, 'on_the_way'],
    ['assigned', { payment_method: 'kaspi_link', payment_status: 'unpaid' }, false, 'on_the_way'],
    ['assigned', cash, false, 'on_the_way'],
    ['arrived', kaspi, false, 'arrived'],
    ['in_progress', cash, false, 'in_progress'],
    ['completed', cash, false, 'pay_cash'],
    ['completed', { payment_method: 'cash', payment_status: 'paid' }, false, 'completed'],
    ['completed', kaspi, false, 'completed'],
    ['cancelled', kaspi, false, 'cancelled'],
    ['no_driver', cash, false, 'no_driver'],
  ] as const)('%s + %j (seen %s) → %s', (status, payment, seen, expected) => {
    expect(rideScreen({ status, ...payment }, { driverFoundSeen: seen })).toBe(expected)
  })

  it('treats searching after assigned or arrived as a release by the driver', () => {
    expect(wasReleased('assigned', 'searching')).toBe(true)
    expect(wasReleased('arrived', 'searching')).toBe(true)
    expect(wasReleased(undefined, 'searching')).toBe(false)
    expect(wasReleased('searching', 'searching')).toBe(false)
    expect(wasReleased('assigned', 'arrived')).toBe(false)
  })

  it('keeps polling an unpaid cash ride after completion only', () => {
    expect(needsPolling({ status: 'completed', ...cash })).toBe(true)
    expect(needsPolling({ status: 'completed', ...kaspi })).toBe(false)
    expect(needsPolling({ status: 'assigned', ...kaspi })).toBe(true)
    expect(needsPolling({ status: 'cancelled', ...cash })).toBe(false)
  })
})

describe('order', () => {
  it('builds the order body with the tariff and payment method', () => {
    expect(buildRideOrder({ quoteId: 'q1', tariff: 'comfort_plus', paymentMethod: 'kaspi_link' })).toEqual({
      quote_id: 'q1',
      payment_method: 'kaspi_link',
      tariff: 'comfort_plus',
    })
  })

  it('labels the button with the tariff and the method', () => {
    expect(orderButtonLabel('economy', 'kaspi_link')).toBe('Заказать Эконом · Kaspi')
    expect(orderButtonLabel('comfort_plus', 'cash')).toBe('Заказать Комфорт+ · Наличные')
  })

  it('turns quote options into four tariff cards in API order', () => {
    const options = tariffOptions({
      options: [
        { tariff: 'economy', amount_kzt: 2200 },
        { tariff: 'comfort', amount_kzt: 2925 },
        { tariff: 'comfort_plus', amount_kzt: 3650 },
        { tariff: 'business', amount_kzt: 4800 },
      ],
    })
    expect(options).toEqual([
      { id: 'economy', name: 'Эконом', price: '2 200 ₸' },
      { id: 'comfort', name: 'Комфорт', price: '2 925 ₸' },
      { id: 'comfort_plus', name: 'Комфорт+', price: '3 650 ₸' },
      { id: 'business', name: 'Бизнес', price: '4 800 ₸' },
    ])
  })

  it('opens the Kaspi link in a new tab only for Kaspi', () => {
    const open = vi.fn()
    expect(openKaspiLink('cash', 'https://pay.kaspi.kz/pay/x', open)).toBe('not_needed')
    expect(open).not.toHaveBeenCalled()
    expect(openKaspiLink('kaspi_link', null, open)).toBe('unavailable')
    expect(open).not.toHaveBeenCalled()
    expect(openKaspiLink('kaspi_link', 'https://pay.kaspi.kz/pay/x', open)).toBe('opened')
    expect(open).toHaveBeenCalledWith('https://pay.kaspi.kz/pay/x', '_blank', 'noopener,noreferrer')
  })
})

describe('format', () => {
  it('formats prices and distances like the mockups', () => {
    expect(formatPrice(2200)).toBe('2 200 ₸')
    expect(formatPrice(0)).toBe('0 ₸')
    expect(formatKm(10_000)).toBe('10,0 км')
    expect(formatKm(4_120)).toBe('4,1 км')
    expect(formatKmCompact(10_000)).toBe('10 км')
    expect(formatKmCompact(4_120)).toBe('4,1 км')
    expect(formatMinutes(1500)).toBe('25 мин')
    expect(formatMinutes(10)).toBe('1 мин')
  })

  it('prints Almaty time and dates', () => {
    expect(formatClock('2026-11-03T09:20:00Z')).toBe('14:20')
    expect(formatRideDate('2026-11-03T09:20:00Z')).toBe('3 ноября, 14:20')
  })

  it('labels history days in Almaty', () => {
    const now = Date.parse('2026-11-03T09:20:00Z')
    expect(historyDayLabel('2026-11-03T04:05:00Z', now)).toBe('СЕГОДНЯ')
    expect(historyDayLabel('2026-11-02T17:41:00Z', now)).toBe('ВЧЕРА')
    expect(historyDayLabel('2026-11-01T10:00:00Z', now)).toBe('1 НОЯБРЯ')
  })

  it('counts down, estimates the pickup and the progress', () => {
    expect(formatCountdown(165)).toBe('02:45')
    expect(formatCountdown(-3)).toBe('00:00')
    expect(pickupEtaMinutes({ latitude: 43.266, longitude: 76.936 }, { latitude: 43.2545, longitude: 76.936 })).toBe(4)
    expect(elapsedShare('2026-11-03T09:20:00Z', 1500, Date.parse('2026-11-03T09:27:00Z'))).toBeCloseTo(0.28)
    expect(elapsedShare(null, 1500)).toBe(0)
  })

  it('shortens and declines driver names', () => {
    expect(shortName('Арман Нурланов')).toBe('Арман Н.')
    expect(shortName(null)).toBe('Водитель')
    expect(withName('Арман Нурланов')).toBe('с Арманом')
    expect(withName('Алексей')).toBe('с Алексеем')
    expect(withName('Дина')).toBe('с Диной')
    expect(initials('Айгерим Жумабаева')).toBe('АЖ')
  })
})

describe('rating', () => {
  it('builds the rating body: unique tags, trimmed comment or null', () => {
    expect(buildRating(4, ['polite', 'clean_car', 'polite'], '  ')).toEqual({ stars: 4, tags: ['polite', 'clean_car'], comment: null })
    expect(buildRating(5, [], ' Спасибо! ')).toEqual({ stars: 5, tags: [], comment: 'Спасибо!' })
    expect(() => buildRating(0, [], '')).toThrow(RangeError)
  })

  it('toggles tags', () => {
    expect(toggleTag(['polite'], 'clean_car')).toEqual(['polite', 'clean_car'])
    expect(toggleTag(['polite', 'clean_car'], 'polite')).toEqual(['clean_car'])
  })
})

describe('history', () => {
  it('maps filters to statuses', () => {
    expect(filterStatuses('all')).toBeUndefined()
    expect(filterStatuses('completed')).toEqual(['completed'])
    expect(filterStatuses('cancelled')).toEqual(['cancelled', 'no_driver'])
  })

  it('shows the payment state of a ride', () => {
    expect(ridePill({ status: 'completed', payment_status: 'paid' })).toEqual({ tone: 'success', text: 'Оплачено' })
    expect(ridePill({ status: 'completed', payment_status: 'unpaid' })).toEqual({ tone: 'warning', text: 'Не оплачено' })
    expect(ridePill({ status: 'cancelled', payment_status: 'refunded' })).toEqual({ tone: 'info', text: 'Возвращено' })
    expect(ridePill({ status: 'cancelled', payment_status: 'unpaid' })).toEqual({ tone: 'neutral', text: 'Отменена' })
  })

  it('prints price and meta, a dash for rides that did not happen', () => {
    const base = { created_at: '2026-11-03T09:20:00Z', amount_kzt: 2200, payment_method: 'cash' } as const
    expect(historyPrice({ ...base, status: 'completed' })).toBe('2 200 ₸')
    expect(historyPrice({ ...base, status: 'cancelled' })).toBe('—')
    expect(historyMeta({ ...base, status: 'completed' })).toBe('14:20 · Наличные')
    expect(historyMeta({ ...base, status: 'no_driver' })).toBe('14:20')
  })

  it('groups rides by day keeping their order', () => {
    const now = Date.parse('2026-11-03T09:20:00Z')
    const rides = [{ created_at: '2026-11-03T09:00:00Z' }, { created_at: '2026-11-03T04:00:00Z' }, { created_at: '2026-11-02T13:00:00Z' }]
    expect(groupByDay(rides, now).map(([label, items]) => [label, items.length])).toEqual([
      ['СЕГОДНЯ', 2],
      ['ВЧЕРА', 1],
    ])
  })
})

describe('places', () => {
  it('fills suggestions with popular places and remembers recent ones', () => {
    const items = new Map<string, string>()
    const storage = {
      getItem: (key: string) => items.get(key) ?? null,
      setItem: (key: string, value: string) => void items.set(key, value),
    } as Storage
    expect(suggestedPlaces(readRecentPlaces(storage))).toEqual(POPULAR_PLACES)
    rememberPlace({ id: 'x', title: 'Dostyk Plaza', subtitle: 'пр. Достык, 111', point: { latitude: 43.23, longitude: 76.95 } }, storage)
    expect(suggestedPlaces(readRecentPlaces(storage)).map((place) => place.title)).toEqual(['Dostyk Plaza', 'Mega Alma-Ata'])
  })
})

describe('errors', () => {
  it('uses the mockup text when routing is down and the dictionary otherwise', () => {
    expect(routeErrorText(new ApiError(503, 'routing_unavailable', 'x'))).toBe(
      'Сервис маршрутов сейчас недоступен. Попробуйте ещё раз через минуту.',
    )
    expect(routeErrorText(new ApiError(422, 'route_points_identical', 'x'))).toBe('Точки посадки и назначения совпадают.')
  })
})

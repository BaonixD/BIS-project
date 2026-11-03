import { describe, expect, it } from 'vitest'
import { buildRatingBody } from '@/hooks/use-driver-rating'
import { formatMoney } from '@/lib/format'
import { driverFixture, offerFixture, rideFixture, summaryFixture } from '@/test/driver-fixtures'
import { paymentSummary, rideStep, selectDriverScreen } from './driver-screen'
import { formatWait, pickupLine } from './pickup-eta'
import { buildReleaseBody } from './release'
import { settingsForm, settingsUpdate } from './settings-form'
import {
  almatyDayStart,
  formatRideTime,
  formatSpan,
  periodStart,
  ridePill,
  ridesWord,
  summarizeShift,
} from './shift-stats'

describe('selectDriverScreen', () => {
  const online = driverFixture({ online: true })

  it('shows the review screen until an admin approves the driver', () => {
    const pending = driverFixture({ approval_status: 'pending', online: false })
    expect(selectDriverScreen({ driver: pending, ride: null, offer: null }).kind).toBe('pending')
  })

  it('separates offline, waiting and an open offer', () => {
    expect(selectDriverScreen({ driver: driverFixture(), ride: null, offer: null }).kind).toBe('offline')
    expect(selectDriverScreen({ driver: online, ride: null, offer: null }).kind).toBe('online')
    expect(selectDriverScreen({ driver: online, ride: null, offer: offerFixture() })).toEqual({
      kind: 'offer',
      offer: offerFixture(),
    })
    const answered = offerFixture({ status: 'expired' })
    expect(selectDriverScreen({ driver: online, ride: null, offer: answered }).kind).toBe('online')
  })

  it.each(['assigned', 'arrived', 'in_progress'] as const)('keeps a %s ride on the ride screen, over any offer', (status) => {
    const screen = selectDriverScreen({ driver: online, ride: rideFixture({ status }), offer: offerFixture() })
    expect(screen.kind).toBe('ride')
  })

  it('reports a ride the passenger cancelled', () => {
    expect(selectDriverScreen({ driver: online, ride: rideFixture({ status: 'cancelled' }), offer: null }).kind).toBe(
      'cancelled',
    )
  })

  it('asks for the cash after a completed cash ride, then moves on to the rating', () => {
    const ride = rideFixture({ status: 'completed', payment_method: 'cash', payment_status: 'unpaid' })
    expect(selectDriverScreen({ driver: online, ride, offer: null }).kind).toBe('collect-cash')
    expect(selectDriverScreen({ driver: online, ride, offer: null, paymentStatus: 'paid' })).toEqual({
      kind: 'completed',
      ride,
      paidBy: 'cash',
    })
  })

  it('never asks for money on a Kaspi ride: it was charged at assignment', () => {
    const ride = rideFixture({ status: 'completed', payment_method: 'kaspi_link', payment_status: 'paid' })
    expect(selectDriverScreen({ driver: online, ride, offer: null })).toEqual({ kind: 'completed', ride, paidBy: 'kaspi' })
    const stale = rideFixture({ status: 'completed', payment_method: 'kaspi_link', payment_status: 'unpaid' })
    expect(selectDriverScreen({ driver: online, ride: stale, offer: null }).kind).toBe('completed')
  })

  it('maps the status onto the four stepper steps', () => {
    expect(['assigned', 'arrived', 'in_progress', 'completed'].map((s) => rideStep(s as never))).toEqual([0, 1, 2, 3])
  })

  it('tells the driver whether to collect the money', () => {
    const amount = formatMoney(2200)
    expect(paymentSummary(rideFixture())).toBe(`Наличные · ${amount} · получить после поездки`)
    expect(paymentSummary(rideFixture({ payment_method: 'kaspi_link' }))).toBe(`Kaspi · уже оплачено · ${amount}`)
  })
})

describe('shift statistics (Asia/Almaty)', () => {
  it('starts the day at Almaty midnight', () => {
    expect(almatyDayStart(new Date('2026-11-03T20:30:00Z')).toISOString()).toBe('2026-11-03T19:00:00.000Z')
    expect(almatyDayStart(new Date('2026-11-03T18:59:00Z')).toISOString()).toBe('2026-11-02T19:00:00.000Z')
  })

  it('builds created_from for today, the week and everything', () => {
    const now = new Date('2026-11-03T09:00:00Z')
    expect(periodStart('today', now)).toBe('2026-11-02T19:00:00.000Z')
    expect(periodStart('week', now)).toBe('2026-10-27T19:00:00.000Z')
    expect(periodStart('all', now)).toBeUndefined()
  })

  it('counts completed rides only', () => {
    const stats = summarizeShift([
      summaryFixture({ amount_kzt: 2200, duration_s: 1500 }),
      summaryFixture({ amount_kzt: 1840, duration_s: 1200 }),
      summaryFixture({ amount_kzt: 2420, duration_s: 1620 }),
      summaryFixture({ status: 'cancelled', amount_kzt: 9999, duration_s: 9999 }),
    ])
    expect(stats).toEqual({ rides: 3, earnedKzt: 6460, drivingS: 4320 })
  })

  it('formats spans and plurals like the mockup', () => {
    expect(formatSpan(8100)).toBe('2 ч 15 мин')
    expect(formatSpan(4320)).toBe('1 ч 12 мин')
    expect(formatSpan(3600)).toBe('1 ч')
    expect(formatSpan(59)).toBe('0 мин')
    expect([1, 3, 5, 11, 21, 22].map(ridesWord)).toEqual(['поездка', 'поездки', 'поездок', 'поездок', 'поездка', 'поездки'])
  })

  it('shows only the time for today and adds the date before', () => {
    const now = new Date('2026-11-03T12:00:00Z')
    expect(formatRideTime('2026-11-03T09:20:00Z', now)).toBe('14:20')
    expect(formatRideTime('2026-11-01T09:20:00Z', now)).toMatch(/^1 нояб\.?, 14:20$/)
  })

  it('labels history rows by whether the money is in', () => {
    expect(ridePill(summaryFixture())).toEqual({ tone: 'success', label: 'Оплачено' })
    expect(ridePill(summaryFixture({ payment_method: 'cash' }))).toEqual({ tone: 'success', label: 'Получено' })
    expect(ridePill(summaryFixture({ payment_method: 'cash', payment_status: 'unpaid' }))).toEqual({
      tone: 'warning',
      label: 'Ожидает',
    })
    expect(ridePill(summaryFixture({ status: 'cancelled' })).label).toBe('Отменена')
  })
})

describe('request bodies', () => {
  it('builds the release reason from the chip and the comment', () => {
    expect(buildReleaseBody('Поломка', '  ')).toEqual({ reason: 'Поломка' })
    expect(buildReleaseBody('Пассажир не вышел', ' ждал 10 минут ')).toEqual({ reason: 'Пассажир не вышел: ждал 10 минут' })
    expect(buildReleaseBody('Другое', 'Пробило колесо')).toEqual({ reason: 'Пробило колесо' })
    expect(buildReleaseBody('Другое', '')).toEqual({ reason: 'Другое' })
    expect(buildReleaseBody('Поломка', 'x'.repeat(300)).reason).toHaveLength(200)
  })

  it('builds the passenger rating', () => {
    expect(buildRatingBody(5, ['clean', 'on_time', 'clean'])).toEqual({ stars: 5, tags: ['on_time', 'clean'], comment: null })
    expect(buildRatingBody(9, [], '  спасибо ')).toEqual({ stars: 5, tags: [], comment: 'спасибо' })
    expect(buildRatingBody(0, new Set(['polite'] as const)).stars).toBe(1)
  })

  it('splits «Toyota Camry» into make and model and keeps the year', () => {
    const form = settingsForm(driverFixture())
    expect(form.car).toBe('Toyota Camry')
    expect(settingsUpdate({ ...form, car: 'Hyundai Elantra N', phone: ' ' })).toEqual({
      full_name: 'Арман Нурланов',
      phone: undefined,
      license_number: 'KZ 12345678',
      vehicle: { make: 'Hyundai', model: 'Elantra N', color: 'белый', plate_number: '123 ABC 02', year: 2020 },
    })
    expect(settingsUpdate({ ...form, car: 'Toyota' }).vehicle).toBeUndefined()
  })
})

describe('pickup line and waiting timer', () => {
  it('estimates the way to the pickup', () => {
    expect(pickupLine(null, { latitude: 43.24, longitude: 76.91 })).toBe('Подача рядом')
    expect(pickupLine({ latitude: 43.24, longitude: 76.91 }, { latitude: 43.2508, longitude: 76.91 })).toBe(
      'Подача 1,2 км · ~4 мин',
    )
  })

  it('counts the wait since arrival', () => {
    expect(formatWait('2026-11-03T09:00:00Z', Date.parse('2026-11-03T09:02:15Z'))).toBe('02:15')
    expect(formatWait(null, 0)).toBe('00:00')
  })
})

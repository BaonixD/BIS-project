import { afterEach, expect, it, vi } from 'vitest'
import { setLocale } from './core'
import { formatRideDate, historyDayLabel } from '@/pages/passenger/model/format'
import { formatRideTime } from '@/pages/driver/shift-stats'
import { adminDate } from '@/pages/admin/admin-model'
import { formatDateTime } from '@/lib/format'

afterEach(() => {
  setLocale('ru')
  vi.restoreAllMocks()
})

it('shows Kazakh month names when the browser returns a placeholder for kk-KZ', () => {
  const original = Intl.DateTimeFormat
  vi.spyOn(Intl, 'DateTimeFormat').mockImplementation(function (locales, options) {
    const formatter = new original(locales, options)
    if (locales === 'kk-KZ') Object.defineProperty(formatter, 'format', { value: () => 'M11 5' })
    return formatter
  })
  setLocale('kk')
  const date = '2026-11-05T06:05:00Z'
  const now = new Date('2026-11-15T06:00:00Z')
  expect(historyDayLabel(date, now.getTime())).toBe('5 ҚАРАША')
  expect(formatRideDate(date)).toBe('5 қараша, 11:05')
  expect(formatRideTime(date, now)).toBe('5 қараша, 11:05')
  expect(adminDate(date)).toBe('5 қараша 2026, 11:05')
  expect(formatDateTime(date)).toBe('05.11.2026, 11:05')
})

it.each([
  ['01', 'ҚАҢТАР'],
  ['02', 'АҚПАН'],
  ['03', 'НАУРЫЗ'],
  ['04', 'СӘУІР'],
  ['05', 'МАМЫР'],
  ['06', 'МАУСЫМ'],
  ['07', 'ШІЛДЕ'],
  ['08', 'ТАМЫЗ'],
  ['09', 'ҚЫРКҮЙЕК'],
  ['10', 'ҚАЗАН'],
  ['11', 'ҚАРАША'],
  ['12', 'ЖЕЛТОҚСАН'],
])('formats Kazakh month %s consistently', (month, expected) => {
  setLocale('kk')
  expect(historyDayLabel(`2026-${month}-05T06:00:00Z`, Date.parse('2027-01-15T00:00:00Z'))).toBe(
    `5 ${expected}`,
  )
})

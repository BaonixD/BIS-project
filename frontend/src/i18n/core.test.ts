import { afterEach, describe, expect, it } from 'vitest'
import { getLocale, LOCALE_STORAGE_KEY, setLocale, translate } from './core'
import { en, kk } from './messages'
import { RIDE_STATUS_LABELS } from '@/lib/labels'
import { formatDistance } from '@/lib/format'
import {
  formatKm,
  formatKmCompact,
  formatPrice,
  historyDayLabel,
  withName,
} from '@/pages/passenger/model/format'
import { ridesWord } from '@/pages/driver/shift-stats'
import { errorMessage } from '@/api/error-messages'
import { ApiError } from '@/api/errors'
import { memoryStorage } from '@/test/fake-api'
import { vi } from 'vitest'

vi.stubGlobal('localStorage', memoryStorage())
afterEach(() => setLocale('ru'))

describe('translation catalogs', () => {
  it('covers the same messages and interpolation parameters in both languages', () => {
    expect(Object.keys(kk).sort()).toEqual(Object.keys(en).sort())
    const placeholders = (value: string) =>
      [...value.matchAll(/\{\w+\}/g)].map((match) => match[0]).sort()
    for (const [source, english] of Object.entries(en)) {
      expect(english.trim(), source).not.toBe('')
      expect(kk[source]?.trim(), source).not.toBe('')
      expect(placeholders(english), source).toEqual(placeholders(source))
      expect(placeholders(kk[source]!), source).toEqual(placeholders(source))
    }
  })

  it('uses natural booking, vehicle and driver terminology', () => {
    expect(translate('en', 'Выйти на линию')).toBe('Go online')
    expect(translate('en', 'Уйти с линии')).toBe('Go offline')
    expect(translate('en', 'Класс машины')).toBe('Car class')
    expect(translate('en', 'Тариф')).toBe('Ride type')
    expect(translate('en', 'Отказаться от заказа')).toBe('Cancel ride')
    expect(translate('en', 'Заказать {p0} · {p1}', { p0: 'Comfort', p1: 'Cash' })).toBe(
      'Book Comfort · Cash',
    )
    expect(translate('kk', 'Войти')).toBe('Кіру')
    expect(translate('kk', 'Пассажир')).toBe('Жолаушы')
    expect(translate('en', ' Повторите через {p0} мин.', { p0: 2 })).toBe(' Try again in 2 min.')
  })
})

describe('language preference and formatting', () => {
  it('persists the preference and sets the document language', () => {
    setLocale('kk')
    expect(getLocale()).toBe('kk')
    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('kk')
    expect(document.documentElement.lang).toBe('kk')
  })

  it('updates status labels, errors and units immediately', () => {
    setLocale('en')
    expect(RIDE_STATUS_LABELS().assigned).toBe('Your driver is on the way')
    expect(formatDistance(4100)).toBe('4.1 km')
    expect(formatKm(4100)).toBe('4.1 km')
    expect(formatKmCompact(10000)).toBe('10 km')
    expect(formatPrice(2200)).toBe('2,200 ₸')
    expect(ridesWord(1)).toBe('ride')
    expect(ridesWord(5)).toBe('rides')
    const error = new ApiError(403, 'account_blocked', 'blocked')
    expect(errorMessage(error)).toBe('Your account has been blocked. Contact an administrator.')
    setLocale('kk')
    expect(RIDE_STATUS_LABELS().assigned).toBe('Жүргізуші сізге келе жатыр')
    expect(ridesWord(5)).toBe('сапар')
  })

  it('keeps user names intact in English and groups history in Almaty time', () => {
    setLocale('en')
    expect(withName('Алия Садыкова')).toBe('with Алия')
    const now = Date.parse('2026-11-15T00:00:00+05:00')
    expect(historyDayLabel('2026-11-14T20:00:00Z', now)).toBe('TODAY')
    setLocale('kk')
    expect(historyDayLabel('2026-11-14T20:00:00Z', now)).toBe('БҮГІН')
  })
})

import { getIntlLocale, getLocale } from './core'

const KAZAKH_MONTHS = [
  'қаңтар',
  'ақпан',
  'наурыз',
  'сәуір',
  'мамыр',
  'маусым',
  'шілде',
  'тамыз',
  'қыркүйек',
  'қазан',
  'қараша',
  'желтоқсан',
] as const

/** App dates use explicit Kazakh months: some browsers return codes such as M11. */
export function dateFormatter(options: Intl.DateTimeFormatOptions) {
  const timeZone = options.timeZone ?? 'Asia/Almaty'
  if (getLocale() !== 'kk')
    return new Intl.DateTimeFormat(getIntlLocale(), { ...options, timeZone })
  const hasDate = Boolean(options.day || options.month || options.year || options.dateStyle)
  if (!hasDate) return new Intl.DateTimeFormat('en-GB', { ...options, timeZone })

  return {
    format(value: number | Date = Date.now()): string {
      const parts = new Intl.DateTimeFormat('en-GB', {
        timeZone,
        day: 'numeric',
        month: 'numeric',
        year: 'numeric',
      }).formatToParts(value)
      const part = (type: string) => parts.find((item) => item.type === type)!.value
      const day = String(Number(part('day')))
      const month = Number(part('month'))
      const year = part('year')
      const namedMonth =
        options.month === 'long' ||
        options.month === 'short' ||
        (options.dateStyle && options.dateStyle !== 'short')
      const date = namedMonth
        ? `${day} ${KAZAKH_MONTHS[month - 1]}${options.year || options.dateStyle ? ` ${year}` : ''}`
        : `${day.padStart(2, '0')}.${String(month).padStart(2, '0')}.${year}`
      if (!options.timeStyle && !options.hour) return date
      const time = new Intl.DateTimeFormat('en-GB', {
        timeZone,
        ...(options.timeStyle
          ? { timeStyle: options.timeStyle }
          : { hour: options.hour, minute: options.minute, second: options.second }),
      }).format(value)
      return `${date}, ${time}`
    },
  }
}

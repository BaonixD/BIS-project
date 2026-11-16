import type { RouteResult } from '@/api'
import { useNow } from '@/hooks/use-countdown'
import { t, useLocale } from '@/i18n/core'
import { formatClock, formatKmCompact, formatMinutes } from '@/pages/passenger/model/format'

/** Before booking, arrival assumes departure now: driver pickup time is not known yet. */
export function RouteArrivalLabel({ route }: { route: RouteResult }) {
  useLocale()
  const now = useNow(30_000)
  return (
    <section
      aria-label={t('Прогноз прибытия')}
      className="flex flex-col items-center gap-1 text-center"
    >
      <p className="text-body-medium">
        {t('Прибытие ≈{p0}', { p0: formatClock(now + route.duration_s * 1000) })}
      </p>
      <p className="text-caption">
        {formatMinutes(route.duration_s)} · {formatKmCompact(route.distance_m)}
      </p>
      <p className="text-[11px] leading-4 opacity-70">{t('Если выехать сейчас · без пробок')}</p>
    </section>
  )
}

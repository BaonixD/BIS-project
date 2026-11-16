import type { RideDetails } from '@/api'
import { useRideEstimate, estimateIsFresh } from '@/hooks/use-ride-estimate'
import { t, useLocale } from '@/i18n/core'
import { formatClock, formatKm, formatMinutes } from '@/pages/passenger/model/format'
import { useNow } from '@/hooks/use-countdown'

export function RideEstimate({ ride }: { ride: RideDetails }) {
  useLocale()
  const active = ride.status === 'assigned' || ride.status === 'in_progress'
  const now = useNow(1000, active)
  const query = useRideEstimate(ride)
  const data = query.data
  const valid = data && !query.isError && estimateIsFresh(data, now)
  const expired =
    valid && data.arrival_at && Date.parse(data.arrival_at) <= now && data.duration_s !== 0
  const seconds =
    valid && data.arrival_at ? Math.max(0, (Date.parse(data.arrival_at) - now) / 1000) : null
  if (ride.status === 'cancelled' || ride.status === 'no_driver') return null
  const finishedSeconds =
    ride.started_at && ride.completed_at
      ? Math.max(0, (Date.parse(ride.completed_at) - Date.parse(ride.started_at)) / 1000)
      : null
  return (
    <section className="w-full rounded-lg bg-bg-subtle p-4" aria-label={t('Время и расстояние')}>
      <p className="mb-3 text-callout text-text-secondary">
        {t(active ? (ride.status === 'assigned' ? 'До подачи' : 'До прибытия') : 'Маршрут поездки')}
      </p>
      <dl className="grid grid-cols-3 gap-3">
        <div>
          <dt className="text-caption text-text-secondary">{t('Расстояние')}</dt>
          <dd className="text-body-medium">
            {active
              ? valid && data.distance_m != null
                ? formatKm(data.distance_m)
                : '—'
              : formatKm(ride.route.distance_m)}
          </dd>
        </div>
        <div>
          <dt className="text-caption text-text-secondary">{t('Время')}</dt>
          <dd className="text-body-medium">
            {active
              ? seconds !== null && !expired
                ? seconds === 0
                  ? t('Рядом')
                  : formatMinutes(seconds)
                : '—'
              : formatMinutes(finishedSeconds ?? ride.route.duration_s)}
          </dd>
        </div>
        <div>
          <dt className="text-caption text-text-secondary">{t('Прибытие')}</dt>
          <dd className="text-body-medium">
            {valid && data.arrival_at && !expired ? `~${formatClock(data.arrival_at)}` : '—'}
          </dd>
        </div>
      </dl>
      {active && (
        <p className="mt-3 text-caption text-text-secondary" role="status">
          {t(
            expired
              ? 'Время уточняется'
              : !valid
                ? query.isFetching
                  ? 'Обновляем время'
                  : 'Время недоступно'
                : data.source === 'approximate'
                  ? 'Приблизительно по расстоянию'
                  : data.route?.traffic_mode === 'live_or_typical'
                    ? 'Примерное время, с учётом дорожной ситуации'
                    : 'Без учёта актуальных пробок',
          )}
        </p>
      )}
    </section>
  )
}

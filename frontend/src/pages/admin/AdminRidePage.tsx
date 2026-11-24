import { t, useLocale } from '@/i18n/core'
import type { ReactNode } from 'react'
import { adminDate } from './admin-model'
import { Link, useParams } from 'react-router'
import { ArrowLeft } from 'lucide-react'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { RouteTitle } from '@/components/driver/RouteTitle'
import { MapView } from '@/components/map/MapView'
import { StatusPill } from '@/components/ui-kit'
import { useRide } from '@/hooks/use-rides'
import { useAdminDriver, useAdminUser } from '@/hooks/use-admin'
import { TARIFF_LABELS } from '@/api/driver-types'
import { formatMoney } from '@/lib/format'
import { rideStatusPill } from './admin-format'
import { adminPayment } from './admin-model'
import { AdminLayout, AdminLoading, CopyId, FactList, RidesLink } from './admin-controls'
export function AdminRidePage() {
  useLocale()
  const { rideId } = useParams()
  const query = useRide(rideId)
  const ride = query.data
  const passenger = useAdminUser(ride?.passenger_id)
  const driver = useAdminDriver(ride?.driver_id ?? undefined)
  const pill = ride ? rideStatusPill(ride.status) : null
  return (
    <AdminLayout
      title={t('Детали поездки')}
      description={t('Маршрут, участники и время прохождения этапов.')}
      refreshing={query.isFetching}
      onRefresh={() => void query.refetch()}
    >
      <Link to="/admin/rides" className="inline-flex items-center gap-2 text-callout">
        <ArrowLeft className="size-4" />
        {t('Все поездки')}
      </Link>
      <ErrorAlert error={query.error} />
      {query.isPending && <AdminLoading />}
      {ride && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <StatusPill tone={pill!.tone}>{pill!.label}</StatusPill>
            <CopyId value={ride.id} />
          </div>
          <div className="grid items-start gap-5 lg:grid-cols-2">
            <section className="overflow-hidden rounded-lg bg-bg-canvas">
              <div className="h-56 bg-map-land">
                <MapView
                  pickup={ride.pickup}
                  dropoff={ride.dropoff}
                  route={ride.route}
                  center={ride.pickup}
                  insets={{ top: 0, right: 0, bottom: 0, left: 0 }}
                />
              </div>
              <div className="p-5">
                <h2 className="text-headline">
                  <RouteTitle pickup={ride.pickup} dropoff={ride.dropoff} />
                </h2>
                <FactList
                  items={[
                    [t('Тариф'), TARIFF_LABELS()[ride.tariff]],
                    [t('Стоимость'), formatMoney(ride.amount_kzt)],
                    [t('Оплата'), adminPayment(ride)],
                    [
                      t('Расстояние'),
                      t('{p0} км', { p0: (ride.route.distance_m / 1000).toFixed(1) }),
                    ],
                    [
                      t('Расчётное время'),
                      t('{p0} мин', { p0: Math.ceil(ride.route.duration_s / 60) }),
                    ],
                  ]}
                />
              </div>
            </section>
            <div className="flex flex-col gap-5">
              <section className="rounded-lg bg-bg-canvas p-5">
                <h2 className="text-headline">{t('Участники')}</h2>
                <ErrorAlert error={passenger.error ?? driver.error} />
                <FactList
                  items={[
                    [
                      t('Пассажир'),
                      <Link
                        to={`/admin/users/${ride.passenger_id}`}
                        className="underline underline-offset-4"
                      >
                        {passenger.data?.display_name ??
                          passenger.data?.username ??
                          t('Открыть аккаунт')}
                      </Link>,
                    ],
                    [
                      t('Водитель'),
                      ride.driver_id ? (
                        <Link
                          to={`/admin/drivers/${ride.driver_id}`}
                          className="underline underline-offset-4"
                        >
                          {driver.data?.full_name ?? driver.data?.username ?? t('Открыть профиль')}
                        </Link>
                      ) : (
                        t('Не назначен')
                      ),
                    ],
                    ...(driver.data?.phone
                      ? [
                          [
                            t('Телефон водителя'),
                            <a href={`tel:${driver.data.phone}`} className="underline">
                              {driver.data.phone}
                            </a>,
                          ] as [string, React.ReactNode],
                        ]
                      : []),
                  ]}
                />
                <RidesLink userId={ride.passenger_id} role="passenger">
                  {t('Все поездки пассажира')}
                </RidesLink>
              </section>
              <section className="rounded-lg bg-bg-canvas p-5">
                <h2 className="text-headline">{t('Этапы поездки')}</h2>
                <FactList
                  items={(
                    [
                      [t('Заказ создан'), ride.created_at],
                      [t('Водитель назначен'), ride.assigned_at],
                      [t('Водитель на месте'), ride.arrived_at],
                      [t('Поездка начата'), ride.started_at],
                      [t('Поездка завершена'), ride.completed_at],
                      [t('Поездка отменена'), ride.cancelled_at],
                    ] as [string, string | null][]
                  )
                    // A finished ride shows only what happened; an active one also what is next.
                    .filter(([, at]) => at !== null || !['completed', 'cancelled', 'no_driver'].includes(ride.status))
                    .map(([label, at]): [string, ReactNode] => [label, at ? adminDate(at) : t('ещё нет')])
                    .concat(
                      ride.status === 'no_driver'
                        ? [[t('Итог'), t('Водитель не найден за время поиска')]]
                        : [],
                      ride.cancel_reason ? [[t('Причина отмены'), ride.cancel_reason]] : [],
                    )}
                />
              </section>
            </div>
          </div>
        </>
      )}
    </AdminLayout>
  )
}

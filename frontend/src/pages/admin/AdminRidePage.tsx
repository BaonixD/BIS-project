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
import { AdminLayout, AdminLoading, FactList, RidesLink } from './admin-controls'

export function AdminRidePage() {
  const { rideId } = useParams()
  const query = useRide(rideId)
  const ride = query.data
  const passenger = useAdminUser(ride?.passenger_id)
  const driver = useAdminDriver(ride?.driver_id ?? undefined)
  const pill = ride ? rideStatusPill(ride.status) : null
  return (
    <AdminLayout
      title="Детали поездки"
      description="Маршрут, участники и время прохождения этапов."
      refreshing={query.isFetching}
      onRefresh={() => void query.refetch()}
    >
      <Link to="/admin/rides" className="inline-flex items-center gap-2 text-callout">
        <ArrowLeft className="size-4" />
        Все поездки
      </Link>
      <ErrorAlert error={query.error} />
      {query.isPending && <AdminLoading />}
      {ride && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <StatusPill tone={pill!.tone}>{pill!.label}</StatusPill>
            <span className="select-all break-all font-mono text-caption text-text-secondary">
              {ride.id}
            </span>
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
                    ['Тариф', TARIFF_LABELS[ride.tariff]],
                    ['Стоимость', formatMoney(ride.amount_kzt)],
                    ['Оплата', adminPayment(ride)],
                    ['Расстояние', `${(ride.route.distance_m / 1000).toFixed(1)} км`],
                    ['Расчётное время', `${Math.ceil(ride.route.duration_s / 60)} мин`],
                  ]}
                />
              </div>
            </section>
            <div className="flex flex-col gap-5">
              <section className="rounded-lg bg-bg-canvas p-5">
                <h2 className="text-headline">Участники</h2>
                <ErrorAlert error={passenger.error ?? driver.error} />
                <FactList
                  items={[
                    [
                      'Пассажир',
                      <Link
                        to={`/admin/users/${ride.passenger_id}`}
                        className="underline underline-offset-4"
                      >
                        {passenger.data?.display_name ??
                          passenger.data?.username ??
                          'Открыть аккаунт'}
                      </Link>,
                    ],
                    [
                      'Водитель',
                      ride.driver_id ? (
                        <Link
                          to={`/admin/drivers/${ride.driver_id}`}
                          className="underline underline-offset-4"
                        >
                          {driver.data?.full_name ?? driver.data?.username ?? 'Открыть профиль'}
                        </Link>
                      ) : (
                        'Не назначен'
                      ),
                    ],
                    ...(driver.data?.phone
                      ? [
                          [
                            'Телефон водителя',
                            <a href={`tel:${driver.data.phone}`} className="underline">
                              {driver.data.phone}
                            </a>,
                          ] as [string, React.ReactNode],
                        ]
                      : []),
                  ]}
                />
                <RidesLink userId={ride.passenger_id} role="passenger">
                  Все поездки пассажира
                </RidesLink>
              </section>
              <section className="rounded-lg bg-bg-canvas p-5">
                <h2 className="text-headline">Этапы поездки</h2>
                <FactList
                  items={[
                    ['Заказ создан', adminDate(ride.created_at)],
                    ['Водитель назначен', adminDate(ride.assigned_at)],
                    ['На месте', adminDate(ride.arrived_at)],
                    ['Поездка начата', adminDate(ride.started_at)],
                    ['Завершена', adminDate(ride.completed_at)],
                    ['Отменена', adminDate(ride.cancelled_at)],
                    ...(ride.cancel_reason
                      ? [['Причина отмены', ride.cancel_reason] as [string, string]]
                      : []),
                  ]}
                />
              </section>
            </div>
          </div>
        </>
      )}
    </AdminLayout>
  )
}

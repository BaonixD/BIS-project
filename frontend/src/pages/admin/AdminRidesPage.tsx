import { Link } from 'react-router'
import { ArrowUpRight } from 'lucide-react'
import type { RideStatus } from '@/api'
import type { components } from '@/api/schema'
import { TARIFF_LABELS } from '@/api/driver-types'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { RouteTitle } from '@/components/driver/RouteTitle'
import { Button, Chip, StatusPill } from '@/components/ui-kit'
import { useAdminRides } from '@/hooks/use-admin'
import type { AdminRideFilters } from '@/hooks/query-keys'
import { formatMoney } from '@/lib/format'
import { rideStatusPill } from './admin-format'
import {
  AdminEmpty,
  AdminLayout,
  AdminLoading,
  AdminResults,
  AdminSearch,
  AdminSelect,
} from './admin-controls'
import {
  ADMIN_PAGE_SIZE,
  adminDate,
  adminPayment,
  periodFrom,
  useAdminFilters,
} from './admin-model'

type AdminRide = components['schemas']['AdminRideSummary']
const VIEWS: { id: string; label: string; statuses?: RideStatus[] }[] = [
  {
    id: 'active',
    label: 'Активные',
    statuses: ['searching', 'assigned', 'arrived', 'in_progress'],
  },
  { id: 'all', label: 'Все' },
  { id: 'completed', label: 'Завершённые', statuses: ['completed'] },
  { id: 'cancelled', label: 'Отменённые', statuses: ['cancelled', 'no_driver'] },
]

function RideRow({ ride }: { ride: AdminRide }) {
  const pill = rideStatusPill(ride.status)
  return (
    <tr className="border-t border-border-default text-callout">
      <td className="min-w-56 px-4 py-4">
        <Link
          to={`/admin/rides/${ride.id}`}
          className="flex flex-col gap-1 outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
        >
          <span className="flex items-center gap-2 text-body-medium">
            <RouteTitle pickup={ride.pickup} dropoff={ride.dropoff} />
            <ArrowUpRight className="size-4 shrink-0" />
          </span>
          <span className="text-caption text-text-secondary">
            {adminDate(ride.created_at)} · {TARIFF_LABELS[ride.tariff]}
          </span>
        </Link>
      </td>
      <td className="px-4 py-4">
        <Link
          to={`/admin/users/${ride.passenger_id}`}
          className="underline decoration-border-default underline-offset-4"
        >
          {ride.passenger_name ?? 'Пассажир'}
        </Link>
      </td>
      <td className="px-4 py-4">
        {ride.driver_id ? (
          <Link
            to={`/admin/drivers/${ride.driver_id}`}
            className="underline decoration-border-default underline-offset-4"
          >
            {ride.driver_name ?? 'Водитель'}
          </Link>
        ) : (
          <span className="text-text-secondary">Не назначен</span>
        )}
      </td>
      <td className="whitespace-nowrap px-4 py-4">{formatMoney(ride.amount_kzt)}</td>
      <td className="px-4 py-4">
        <span
          className={
            ride.payment_status === 'unpaid' && ride.status === 'completed'
              ? 'text-accent-danger'
              : 'text-text-secondary'
          }
        >
          {adminPayment(ride)}
        </span>
      </td>
      <td className="px-4 py-4">
        <StatusPill tone={pill.tone}>{pill.label}</StatusPill>
      </td>
    </tr>
  )
}

export function AdminRidesPage() {
  const { params, offset, update, reset } = useAdminFilters()
  const view = VIEWS.find((item) => item.id === params.get('view')) ?? VIEWS[0]!
  const q = params.get('q') ?? ''
  const paymentStatus = params.get('payment_status') ?? ''
  const paymentMethod = params.get('payment_method') ?? ''
  const tariff = params.get('tariff') ?? ''
  const period = params.get('period') ?? ''
  const filters: AdminRideFilters = {
    status: view.statuses,
    q: q || undefined,
    limit: ADMIN_PAGE_SIZE,
    offset,
    created_from: periodFrom(period),
    passenger_id: params.get('passenger_id') || undefined,
    driver_id: params.get('driver_id') || undefined,
  }
  if (['unpaid', 'paid', 'refunded'].includes(paymentStatus))
    filters.payment_status = paymentStatus as AdminRideFilters['payment_status']
  if (['cash', 'kaspi_link'].includes(paymentMethod))
    filters.payment_method = paymentMethod as AdminRideFilters['payment_method']
  if (Object.keys(TARIFF_LABELS).includes(tariff))
    filters.tariff = tariff as AdminRideFilters['tariff']
  const rides = useAdminRides(filters)
  const scoped = Boolean(filters.passenger_id || filters.driver_id)
  return (
    <AdminLayout
      title="Поездки"
      description="Маршруты, участники, оплата и этапы каждой поездки."
      refreshing={rides.isFetching}
      onRefresh={() => void rides.refetch()}
    >
      <div className="flex gap-2 overflow-x-auto">
        {VIEWS.map((item) => (
          <Chip
            key={item.id}
            selected={view.id === item.id}
            onClick={() => update({ view: item.id })}
          >
            {item.label}
          </Chip>
        ))}
      </div>
      {scoped && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-bg-canvas px-4 py-2 text-callout">
          <span>Показаны поездки выбранного {filters.driver_id ? 'водителя' : 'пассажира'}</span>
          <Button
            variant="ghost"
            size="md"
            onClick={() => update({ passenger_id: '', driver_id: '' })}
          >
            Показать всех
          </Button>
        </div>
      )}
      <div className="rounded-lg bg-bg-canvas p-4">
        <AdminSearch
          key={q}
          value={q}
          placeholder="Участник, телефон, госномер или полный ID поездки"
          onSearch={(value) => update({ q: value })}
        />
        <div className="mt-4 grid grid-cols-2 items-end gap-3 md:grid-cols-3 xl:grid-cols-[repeat(4,minmax(0,1fr))_auto]">
          <AdminSelect
            label="Период"
            value={period}
            options={[
              ['', 'За всё время'],
              ['today', 'Сегодня'],
              ['week', 'Последние 7 дней'],
              ['month', 'Последние 30 дней'],
            ]}
            onChange={(value) => update({ period: value })}
          />
          <AdminSelect
            label="Статус оплаты"
            value={paymentStatus}
            options={[
              ['', 'Любой'],
              ['unpaid', 'Не оплачено'],
              ['paid', 'Оплачено'],
              ['refunded', 'Возврат'],
            ]}
            onChange={(value) => update({ payment_status: value })}
          />
          <AdminSelect
            label="Способ оплаты"
            value={paymentMethod}
            options={[
              ['', 'Любой'],
              ['cash', 'Наличные'],
              ['kaspi_link', 'Kaspi'],
            ]}
            onChange={(value) => update({ payment_method: value })}
          />
          <AdminSelect
            label="Тариф"
            value={tariff}
            options={[['', 'Все тарифы'], ...Object.entries(TARIFF_LABELS)]}
            onChange={(value) => update({ tariff: value })}
          />
          <Button variant="ghost" size="md" onClick={reset}>
            Сбросить
          </Button>
        </div>
      </div>
      <ErrorAlert error={rides.error} />
      {rides.isPending && <AdminLoading />}
      {rides.data?.items.length === 0 && (
        <AdminEmpty message="Поездок не найдено" onReset={reset} />
      )}
      {Boolean(rides.data?.items.length) && (
        <div
          aria-busy={rides.isFetching}
          className={`hidden overflow-x-auto rounded-lg bg-bg-canvas lg:block ${rides.isPlaceholderData ? 'pointer-events-none opacity-50' : ''}`}
        >
          <table className="w-full min-w-[960px] text-left">
            <caption className="sr-only">Поездки и статус оплаты</caption>
            <thead>
              <tr className="text-label text-text-tertiary">
                {['МАРШРУТ / ДАТА', 'ПАССАЖИР', 'ВОДИТЕЛЬ', 'СУММА', 'ОПЛАТА', 'СТАТУС'].map(
                  (label) => (
                    <th scope="col" key={label} className="px-4 py-3 font-semibold">
                      {label}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {rides.data?.items.map((ride) => (
                <RideRow key={ride.id} ride={ride} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      <ul
        className={`flex flex-col gap-3 lg:hidden ${rides.isPlaceholderData ? 'pointer-events-none opacity-50' : ''}`}
      >
        {rides.data?.items.map((ride) => {
          const pill = rideStatusPill(ride.status)
          return (
            <li key={ride.id} className="rounded-lg bg-bg-canvas p-4">
              <Link
                to={`/admin/rides/${ride.id}`}
                className="flex flex-col gap-3 outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
              >
                <div className="flex items-center justify-between gap-2">
                  <StatusPill tone={pill.tone}>{pill.label}</StatusPill>
                  <span className="text-body-medium">{formatMoney(ride.amount_kzt)}</span>
                </div>
                <p className="text-callout">
                  <RouteTitle pickup={ride.pickup} dropoff={ride.dropoff} />
                </p>
                <p className="text-caption text-text-secondary">
                  {ride.passenger_name ?? 'Пассажир'} · {ride.driver_name ?? 'Водитель не назначен'}
                </p>
                <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border-default pt-3 text-caption text-text-secondary">
                  <span>{adminDate(ride.created_at)}</span>
                  <span>{adminPayment(ride)}</span>
                </div>
              </Link>
            </li>
          )
        })}
      </ul>
      <AdminResults
        total={rides.data?.total}
        offset={offset}
        busy={rides.isFetching}
        onPage={(value) => update({ offset: String(value) }, true)}
      />
    </AdminLayout>
  )
}

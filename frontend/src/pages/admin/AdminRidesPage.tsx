import { useState } from 'react'
import { Search } from 'lucide-react'
import type { RideStatus, RideSummary } from '@/api'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { RouteTitle } from '@/components/driver/RouteTitle'
import { Screen } from '@/components/driver/Screen'
import { Chip, Input, Skeleton, StatusPill } from '@/components/ui-kit'
import { useAdminRides } from '@/hooks/use-admin'
import { cn } from '@/lib/utils'
import { amountCell, paymentCell, rideStatusPill, rideSubtitle } from './admin-format'
import { useAdminNames } from './admin-people'
import { AdminLogoutButton } from './AdminLogoutButton'

type Filter = 'active' | 'completed' | 'cancelled'

const FILTERS: { id: Filter; mobile: string; desktop: string; statuses: RideStatus[] }[] = [
  { id: 'active', mobile: 'Активные', desktop: 'Активные', statuses: ['searching', 'assigned', 'arrived', 'in_progress'] },
  { id: 'completed', mobile: 'Готово', desktop: 'Завершённые', statuses: ['completed'] },
  { id: 'cancelled', mobile: 'Отмена', desktop: 'Отменённые', statuses: ['cancelled', 'no_driver'] },
]

/** Desktop 7:111 column widths. */
const COLUMNS = [
  { title: 'МАРШРУТ', width: 'w-[380px]' },
  { title: 'ПАССАЖИР', width: 'w-[180px]' },
  { title: 'ВОДИТЕЛЬ', width: 'w-[200px]' },
  { title: 'СУММА', width: 'w-[140px]' },
  { title: 'ОПЛАТА', width: 'w-[160px]' },
  { title: 'СТАТУС', width: 'w-[160px]' },
] as const

function Filters({ value, onChange, desktop }: { value: Filter; onChange: (filter: Filter) => void; desktop?: boolean }) {
  return (
    <div className={cn('flex items-center gap-2', desktop ? 'hidden shrink-0 lg:flex' : 'w-full overflow-x-auto scrollbar-none lg:hidden')}>
      {FILTERS.map((item) => (
        <Chip key={item.id} selected={item.id === value} onClick={() => onChange(item.id)}>
          {desktop ? item.desktop : item.mobile}
        </Chip>
      ))}
    </div>
  )
}

interface Row {
  ride: RideSummary
  passenger: string
  driver: string | null
}

function MobileRow({ row }: { row: Row }) {
  const pill = rideStatusPill(row.ride.status)
  return (
    <li className="flex w-full items-center gap-3 overflow-hidden p-3">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <p className="truncate text-callout text-text-primary">
          <RouteTitle pickup={row.ride.pickup} dropoff={row.ride.dropoff} />
        </p>
        <p className="truncate text-caption text-text-secondary">{rideSubtitle(row.ride, row.passenger, row.driver)}</p>
      </div>
      <StatusPill tone={pill.tone}>{pill.label}</StatusPill>
    </li>
  )
}

function DesktopTable({ rows }: { rows: Row[] }) {
  return (
    <table className="hidden w-full overflow-hidden rounded-lg bg-bg-canvas lg:table">
      <thead>
        <tr className="flex px-6 py-3.5 text-left text-label text-text-tertiary">
          {COLUMNS.map((column) => (
            <th key={column.title} className={cn('shrink-0 font-semibold', column.width)}>
              {column.title}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map(({ ride, passenger, driver }) => {
          const pill = rideStatusPill(ride.status)
          return (
            <tr key={ride.id} className="flex items-center border-t border-solid border-border-default px-6 py-4 text-callout text-text-secondary">
              <td className={cn('shrink-0 truncate pr-4 text-text-primary', COLUMNS[0].width)}>
                <RouteTitle pickup={ride.pickup} dropoff={ride.dropoff} />
              </td>
              <td className={cn('shrink-0 truncate pr-4', COLUMNS[1].width)}>{passenger}</td>
              <td className={cn('shrink-0 truncate pr-4', COLUMNS[2].width)}>{driver ?? '—'}</td>
              <td className={cn('shrink-0', COLUMNS[3].width)}>{amountCell(ride)}</td>
              <td className={cn('shrink-0', COLUMNS[4].width)}>{paymentCell(ride)}</td>
              <td className={cn('flex h-6 shrink-0 items-center', COLUMNS[5].width)}>
                <StatusPill tone={pill.tone}>{pill.label}</StatusPill>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

/** Figma 6:534 (mobile list) and Desktop 7:111 (table): every ride with its people, money and status. */
export function AdminRidesPage() {
  const [filter, setFilter] = useState<Filter>('active')
  const [query, setQuery] = useState('')
  const statuses = FILTERS.find((item) => item.id === filter)?.statuses
  const rides = useAdminRides({ status: statuses, limit: 50 })
  const names = useAdminNames()
  const needle = query.trim().toLowerCase()
  const rows = (rides.data?.items ?? [])
    .map((ride) => ({ ride, passenger: names.passenger(ride.passenger_id), driver: names.driver(ride.driver_id) }))
    .filter((row) => !needle || `${row.passenger} ${row.driver ?? ''}`.toLowerCase().includes(needle))

  return (
    <Screen tone="subtle">
      <div className="mx-auto flex w-full max-w-[390px] flex-col gap-4 px-4 pt-[calc(64px+env(safe-area-inset-top))] pb-6 lg:max-w-none lg:gap-5 lg:px-8 lg:pt-8">
        <div className="flex w-full items-center gap-4">
          <h1 className="min-w-0 flex-1 text-display text-text-primary">Все поездки</h1>
          <AdminLogoutButton />
          <Filters value={filter} onChange={setFilter} desktop />
        </div>
        <Input
          icon={Search}
          placeholder="Поиск по пассажиру или водителю"
          aria-label="Поиск по пассажиру или водителю"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          containerClassName="lg:hidden"
        />
        <Filters value={filter} onChange={setFilter} />
        <ErrorAlert error={rides.error} />
        {rides.isPending && <Skeleton className="h-68 w-full rounded-lg" />}
        {rides.data && rows.length === 0 && (
          <p className="w-full rounded-lg bg-bg-canvas p-5 text-center text-callout text-text-secondary">Поездок нет</p>
        )}
        {rows.length > 0 && (
          <>
            <ul className="flex w-full flex-col overflow-hidden rounded-lg bg-bg-canvas p-2 lg:hidden">
              {rows.map((row) => (
                <MobileRow key={row.ride.id} row={row} />
              ))}
            </ul>
            <DesktopTable rows={rows} />
          </>
        )}
      </div>
    </Screen>
  )
}

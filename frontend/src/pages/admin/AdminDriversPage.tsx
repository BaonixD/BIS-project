import { ADMIN_PAGE_SIZE, useAdminFilters } from './admin-model'
import { Link } from 'react-router'
import { AlertCircle, ChevronRight } from 'lucide-react'
import type { ApprovalStatus } from '@/api'
import type { NextAdminDriver } from '@/api/driver-types'
import { TARIFF_LABELS } from '@/api/driver-types'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Avatar } from '@/components/driver/Avatar'
import { Button, Chip, StatusPill } from '@/components/ui-kit'
import { useAdminDrivers } from '@/hooks/use-admin'
import { vehicleLine } from './admin-format'
import { CarClassSheet } from './CarClassSheet'
import { useApproveFlow } from './use-approve-flow'
import {
  AdminEmpty,
  AdminLayout,
  AdminLoading,
  AdminResults,
  AdminSearch,
  AdminSelect,
} from './admin-controls'

const FILTERS = [
  ['pending', 'На проверке'],
  ['approved', 'Одобрены'],
  ['all', 'Все'],
] as const

function DriverRequest({ driver, onApprove }: { driver: NextAdminDriver; onApprove: () => void }) {
  const name = driver.full_name ?? driver.username
  return (
    <li className="flex flex-col gap-4 rounded-lg bg-bg-canvas p-5">
      <Link
        to={`/admin/drivers/${driver.id}`}
        className="flex items-center gap-3 outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
      >
        <Avatar name={name} size={48} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-body-medium text-text-primary">{name}</p>
          <p className="text-caption text-text-secondary">@{driver.username}</p>
        </div>
        <ChevronRight className="size-5 text-text-tertiary" />
      </Link>
      <div className="flex flex-wrap gap-2">
        <StatusPill
          tone={
            driver.blocked_at
              ? 'danger'
              : driver.approval_status === 'approved'
                ? 'success'
                : 'warning'
          }
        >
          {driver.blocked_at
            ? 'Заблокирован'
            : driver.approval_status === 'approved'
              ? 'Одобрен'
              : 'На проверке'}
        </StatusPill>
        <StatusPill tone={driver.online ? 'info' : 'neutral'}>
          {driver.online ? 'На линии' : 'Не на линии'}
        </StatusPill>
        {driver.vehicle && <StatusPill>{TARIFF_LABELS[driver.vehicle.car_class]}</StatusPill>}
      </div>
      <p className="text-callout text-text-secondary">{vehicleLine(driver)}</p>
      {driver.missing_fields.length > 0 && (
        <p className="flex items-center gap-2 text-caption text-accent-danger">
          <AlertCircle className="size-4" />
          Профиль заполнен не полностью
        </p>
      )}
      <div className="mt-auto grid grid-cols-2 gap-2">
        <Button asChild variant="secondary" size="md">
          <Link to={`/admin/drivers/${driver.id}`}>Подробнее</Link>
        </Button>
        <Button size="md" onClick={onApprove} disabled={Boolean(driver.blocked_at)}>
          {driver.approval_status === 'approved' ? 'Класс машины' : 'Одобрить'}
        </Button>
      </div>
    </li>
  )
}

export function AdminDriversPage() {
  const { params, offset, update, reset } = useAdminFilters()
  const status = params.get('status') ?? 'pending'
  const filter = status === 'approved' ? 'approved' : status === 'all' ? 'all' : 'pending'
  const q = params.get('q') ?? ''
  const online = params.get('online')
  const drivers = useAdminDrivers(filter === 'all' ? undefined : (filter as ApprovalStatus), {
    limit: ADMIN_PAGE_SIZE,
    offset,
    q: q || undefined,
    online: online === 'true' ? true : online === 'false' ? false : undefined,
  })
  const waiting = useAdminDrivers('pending', { limit: 1 })
  const flow = useApproveFlow()
  return (
    <AdminLayout
      title="Водители"
      description="Проверяйте заявки, назначайте класс машины и следите за доступностью."
      refreshing={drivers.isFetching}
      onRefresh={() => {
        void drivers.refetch()
        void waiting.refetch()
      }}
    >
      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map(([id, label]) => (
          <Chip key={id} selected={filter === id} onClick={() => update({ status: id })}>
            {label}
          </Chip>
        ))}
        {(waiting.data?.total ?? 0) > 0 && (
          <StatusPill tone="warning">{waiting.data!.total} ждут</StatusPill>
        )}
      </div>
      <div className="grid items-end gap-3 rounded-lg bg-bg-canvas p-4 sm:grid-cols-[minmax(0,1fr)_180px_auto]">
        <AdminSearch
          key={q}
          value={q}
          placeholder="Имя, логин, телефон или госномер"
          onSearch={(value) => update({ q: value })}
        />
        <AdminSelect
          label="Доступность"
          value={online ?? ''}
          options={[
            ['', 'Любая'],
            ['true', 'На линии'],
            ['false', 'Не на линии'],
          ]}
          onChange={(value) => update({ online: value })}
        />
        <Button variant="ghost" size="md" onClick={reset}>
          Сбросить
        </Button>
      </div>
      <ErrorAlert error={drivers.error} />
      {drivers.isPending && <AdminLoading />}
      {drivers.data?.items.length === 0 && <AdminEmpty onReset={reset} />}
      <ul
        className={`grid gap-4 md:grid-cols-2 xl:grid-cols-3 ${drivers.isPlaceholderData ? 'pointer-events-none opacity-50' : ''}`}
        aria-busy={drivers.isFetching}
      >
        {drivers.data?.items.map((driver) => (
          <DriverRequest key={driver.id} driver={driver} onApprove={() => flow.open(driver)} />
        ))}
      </ul>
      <AdminResults
        total={drivers.data?.total}
        offset={offset}
        busy={drivers.isFetching}
        onPage={(value) => update({ offset: String(value) }, true)}
      />
      {flow.target && (
        <CarClassSheet
          initial={flow.target.vehicle?.car_class ?? 'economy'}
          confirmLabel={flow.target.approval_status === 'approved' ? 'Сохранить класс' : 'Одобрить'}
          busy={flow.busy}
          onConfirm={flow.confirm}
          onClose={flow.close}
        />
      )}
    </AdminLayout>
  )
}

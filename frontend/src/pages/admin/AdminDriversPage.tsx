import { Link } from 'react-router'
import { useState } from 'react'
import type { ApprovalStatus } from '@/api'
import type { NextAdminDriver } from '@/api/next-contract-driver'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Avatar } from '@/components/driver/Avatar'
import { Screen, ScreenColumn } from '@/components/driver/Screen'
import { Button, Chip, Skeleton, StatusPill } from '@/components/ui-kit'
import { useAdminDrivers } from '@/hooks/use-admin'
import { vehicleLine } from './admin-format'
import { CarClassSheet } from './CarClassSheet'
import { useApproveFlow } from './use-approve-flow'

const FILTERS: { id: ApprovalStatus | 'all'; label: string }[] = [
  { id: 'pending', label: 'На проверке' },
  { id: 'approved', label: 'Одобрены' },
  { id: 'all', label: 'Все' },
]

function DriverRequest({ driver, onApprove }: { driver: NextAdminDriver; onApprove: () => void }) {
  const name = driver.full_name ?? driver.username
  return (
    <li className="flex w-full flex-col gap-3 overflow-hidden rounded-lg bg-bg-canvas p-4">
      <div className="flex w-full items-center gap-3">
        <Avatar name={name} size={48} />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <p className="truncate text-body-medium text-text-primary">{name}</p>
          <p className="truncate text-caption text-text-secondary">{vehicleLine(driver)}</p>
        </div>
      </div>
      <div className="flex w-full items-center gap-2">
        <Button asChild variant="secondary" size="md" className="flex-1">
          <Link to={`/admin/drivers/${driver.id}`}>Подробнее</Link>
        </Button>
        <Button size="md" className="flex-1" onClick={onApprove}>
          {driver.approval_status === 'approved' ? 'Класс машины' : 'Одобрить'}
        </Button>
      </div>
    </li>
  )
}

/** Figma 6:444: driver applications and approval with the car class. */
export function AdminDriversPage() {
  const [filter, setFilter] = useState<ApprovalStatus | 'all'>('pending')
  const drivers = useAdminDrivers(filter === 'all' ? undefined : filter, { limit: 50 })
  const waiting = useAdminDrivers('pending', { limit: 1 })
  const flow = useApproveFlow()
  const pendingCount = waiting.data?.total ?? 0

  return (
    <Screen tone="subtle">
      <ScreenColumn className="gap-4 pt-[calc(17px+env(safe-area-inset-top))] pb-6 lg:max-w-2xl lg:pt-8">
        <div className="flex w-full items-center gap-3">
          <h1 className="min-w-0 flex-1 text-display text-text-primary">Водители</h1>
          {pendingCount > 0 && <StatusPill tone="warning">{pendingCount} ждут</StatusPill>}
        </div>
        <div className="flex w-full items-center gap-2 overflow-x-auto scrollbar-none">
          {FILTERS.map((item) => (
            <Chip key={item.id} selected={item.id === filter} onClick={() => setFilter(item.id)}>
              {item.label}
            </Chip>
          ))}
        </div>
        <ErrorAlert error={drivers.error} />
        {drivers.isPending && <Skeleton className="h-34 w-full rounded-lg" />}
        {drivers.data?.items.length === 0 && (
          <p className="w-full rounded-lg bg-bg-canvas p-5 text-center text-callout text-text-secondary">Заявок нет</p>
        )}
        <ul className="flex w-full flex-col gap-4">
          {drivers.data?.items.map((driver) => (
            <DriverRequest key={driver.id} driver={driver} onApprove={() => flow.open(driver)} />
          ))}
        </ul>
      </ScreenColumn>
      {flow.target && (
        <CarClassSheet
          initial={flow.target.vehicle?.car_class ?? 'economy'}
          confirmLabel={flow.target.approval_status === 'approved' ? 'Сохранить класс' : 'Одобрить'}
          busy={flow.busy}
          onConfirm={flow.confirm}
          onClose={flow.close}
        />
      )}
    </Screen>
  )
}

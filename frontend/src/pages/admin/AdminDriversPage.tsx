import { useState } from 'react'
import type { AdminDriver, ApprovalStatus } from '@/api'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { LogoutButton } from '@/components/common/LogoutButton'
import { PageHeader } from '@/components/common/PageHeader'
import { Pagination } from '@/components/common/Pagination'
import { PageContainer } from '@/components/layout/PageContainer'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAdminDrivers, useApproveDriver } from '@/hooks/use-admin'
import { formatDateTime } from '@/lib/format'
import { APPROVAL_STATUS_LABELS, DRIVER_FIELD_LABELS } from '@/lib/labels'

const PAGE_SIZE = 20

function DriverRow({ driver }: { driver: AdminDriver }) {
  const approve = useApproveDriver()
  const vehicle = driver.vehicle
  return (
    <Card className="py-4">
      <CardContent className="grid gap-2 px-4">
        <div className="flex items-center justify-between gap-2">
          <p className="font-medium">{driver.full_name ?? driver.username}</p>
          <Badge variant={driver.approval_status === 'approved' ? 'default' : 'secondary'}>
            {APPROVAL_STATUS_LABELS[driver.approval_status]}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          @{driver.username} · {driver.phone ?? 'нет телефона'} · права {driver.license_number ?? '—'}
        </p>
        <p className="text-sm text-muted-foreground">
          {vehicle ? `${vehicle.make} ${vehicle.model}, ${vehicle.color}, ${vehicle.year} · ${vehicle.plate_number}` : 'Машина не указана'}
        </p>
        {driver.missing_fields.length > 0 && (
          <p className="text-sm">Не заполнено: {driver.missing_fields.map((f) => DRIVER_FIELD_LABELS[f] ?? f).join(', ')}</p>
        )}
        <p className="text-xs text-muted-foreground">Регистрация {formatDateTime(driver.created_at)}</p>
        <ErrorAlert error={approve.error} />
        {driver.approval_status === 'pending' && (
          <Button disabled={approve.isPending} onClick={() => approve.mutate(driver.id)}>
            Допустить
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

export function AdminDriversPage() {
  const [status, setStatus] = useState<ApprovalStatus>('pending')
  const [offset, setOffset] = useState(0)
  const drivers = useAdminDrivers(status, { limit: PAGE_SIZE, offset })

  return (
    <PageContainer>
      <PageHeader title="Водители" action={<LogoutButton />} />
      <Tabs
        value={status}
        onValueChange={(value) => {
          setStatus(value as ApprovalStatus)
          setOffset(0)
        }}
        className="pb-4"
      >
        <TabsList>
          <TabsTrigger value="pending">На допуск</TabsTrigger>
          <TabsTrigger value="approved">Допущены</TabsTrigger>
        </TabsList>
      </Tabs>
      {drivers.isPending && <Skeleton className="h-40" />}
      {drivers.isError && <ErrorAlert error={drivers.error} />}
      {drivers.data && drivers.data.items.length === 0 && <EmptyState>Нет водителей</EmptyState>}
      {drivers.data && (
        <>
          <ul className="grid gap-2">
            {drivers.data.items.map((driver) => (
              <li key={driver.id}><DriverRow driver={driver} /></li>
            ))}
          </ul>
          <Pagination offset={offset} limit={PAGE_SIZE} total={drivers.data.total} onChange={setOffset} />
        </>
      )}
    </PageContainer>
  )
}

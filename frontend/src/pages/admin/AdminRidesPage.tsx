import { useState } from 'react'
import type { RideStatus } from '@/api'
import { PageHeader } from '@/components/common/PageHeader'
import { ALL_STATUSES, RideList, RideStatusFilter } from '@/components/common/RideList'
import { PageContainer } from '@/components/layout/PageContainer'
import { useAdminRides } from '@/hooks/use-admin'

const PAGE_SIZE = 20

export function AdminRidesPage() {
  const [status, setStatus] = useState<RideStatus | typeof ALL_STATUSES>(ALL_STATUSES)
  const [offset, setOffset] = useState(0)
  const rides = useAdminRides({
    status: status === ALL_STATUSES ? undefined : [status],
    limit: PAGE_SIZE,
    offset,
  })

  return (
    <PageContainer>
      <PageHeader title="Все поездки" />
      <div className="pb-4">
        <RideStatusFilter
          value={status}
          onChange={(next) => {
            setStatus(next)
            setOffset(0)
          }}
        />
      </div>
      <RideList query={rides} onOffsetChange={setOffset} />
    </PageContainer>
  )
}

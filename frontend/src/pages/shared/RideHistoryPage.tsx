import { useState } from 'react'
import type { RideStatus, RideSummary } from '@/api'
import { PageHeader } from '@/components/common/PageHeader'
import { ALL_STATUSES, RideList, RideStatusFilter } from '@/components/common/RideList'
import { PageContainer } from '@/components/layout/PageContainer'
import { useRideHistory } from '@/hooks/use-rides'

const PAGE_SIZE = 20

/** `GET /rides` history for passengers and drivers. */
export function RideHistoryPage({ linkTo }: { linkTo?: (ride: RideSummary) => string }) {
  const [status, setStatus] = useState<RideStatus | typeof ALL_STATUSES>(ALL_STATUSES)
  const [offset, setOffset] = useState(0)
  const history = useRideHistory({
    status: status === ALL_STATUSES ? undefined : [status],
    limit: PAGE_SIZE,
    offset,
  })

  return (
    <PageContainer>
      <PageHeader title="Поездки" />
      <div className="pb-4">
        <RideStatusFilter
          value={status}
          onChange={(next) => {
            setStatus(next)
            setOffset(0)
          }}
        />
      </div>
      <RideList query={history} onOffsetChange={setOffset} linkTo={linkTo} />
    </PageContainer>
  )
}

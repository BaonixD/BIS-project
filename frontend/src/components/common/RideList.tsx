import { Link } from 'react-router'
import { ChevronRight } from 'lucide-react'
import type { Page, RideStatus, RideSummary } from '@/api'
import { Card, CardContent } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateTime, formatDistance, formatMoney } from '@/lib/format'
import { PAYMENT_METHOD_LABELS, PAYMENT_STATUS_LABELS, RIDE_STATUS_LABELS } from '@/lib/labels'
import { EmptyState } from './EmptyState'
import { ErrorAlert } from './ErrorAlert'
import { Pagination } from './Pagination'
import { RideStatusBadge } from './RideStatusBadge'

export const ALL_STATUSES = 'all'

export function RideStatusFilter({ value, onChange }: { value: RideStatus | typeof ALL_STATUSES; onChange: (value: RideStatus | typeof ALL_STATUSES) => void }) {
  return (
    <Select value={value} onValueChange={(next) => onChange(next as RideStatus | typeof ALL_STATUSES)}>
      <SelectTrigger className="w-full sm:w-56" aria-label="Статус поездки">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL_STATUSES}>Все статусы</SelectItem>
        {(Object.keys(RIDE_STATUS_LABELS) as RideStatus[]).map((status) => (
          <SelectItem key={status} value={status}>{RIDE_STATUS_LABELS[status]}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function RideRow({ ride }: { ride: RideSummary }) {
  return (
    <div className="flex items-center gap-3">
      <div className="grid flex-1 gap-1">
        <div className="flex items-center gap-2">
          <RideStatusBadge status={ride.status} />
          <span className="text-xs text-muted-foreground">{formatDateTime(ride.created_at)}</span>
        </div>
        <p className="text-sm">
          {formatMoney(ride.amount_kzt)} · {formatDistance(ride.distance_m)}
          {ride.payment_status && ride.payment_method && (
            <span className="text-muted-foreground">
              {' '}· {PAYMENT_METHOD_LABELS[ride.payment_method]}, {PAYMENT_STATUS_LABELS[ride.payment_status].toLowerCase()}
            </span>
          )}
        </p>
      </div>
    </div>
  )
}

interface RideListProps {
  query: { data?: Page<RideSummary>; isPending: boolean; error: unknown }
  onOffsetChange: (offset: number) => void
  linkTo?: (ride: RideSummary) => string
}

export function RideList({ query, onOffsetChange, linkTo }: RideListProps) {
  if (query.isPending) return <Skeleton className="h-40" />
  if (query.error) return <ErrorAlert error={query.error} />
  const page = query.data
  if (!page || page.items.length === 0) return <EmptyState>Поездок пока нет</EmptyState>
  return (
    <>
      <ul className="grid gap-2">
        {page.items.map((ride) => (
          <li key={ride.id}>
            <Card className="py-3">
              <CardContent className="px-4">
                {linkTo ? (
                  <Link to={linkTo(ride)} className="flex items-center gap-2">
                    <div className="flex-1"><RideRow ride={ride} /></div>
                    <ChevronRight className="size-4 text-muted-foreground" aria-hidden />
                  </Link>
                ) : (
                  <RideRow ride={ride} />
                )}
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
      <Pagination offset={page.offset} limit={page.limit} total={page.total} onChange={onOffsetChange} />
    </>
  )
}

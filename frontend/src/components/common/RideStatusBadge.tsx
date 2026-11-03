import type { RideStatus } from '@/api'
import { Badge } from '@/components/ui/badge'
import { RIDE_STATUS_LABELS } from '@/lib/labels'

const VARIANT: Record<RideStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  searching: 'secondary',
  assigned: 'default',
  arrived: 'default',
  in_progress: 'default',
  completed: 'outline',
  cancelled: 'destructive',
  no_driver: 'destructive',
}

export function RideStatusBadge({ status }: { status: RideStatus }) {
  return <Badge variant={VARIANT[status]}>{RIDE_STATUS_LABELS[status]}</Badge>
}

import { useState } from 'react'
import type { RideDetails } from '@/api'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { RideStatusBadge } from '@/components/common/RideStatusBadge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useDriverRideCommand, useReleaseRide, type DriverRideCommand } from '@/hooks/use-rides'
import { formatDistance, formatDuration, formatMoney } from '@/lib/format'

const NEXT_COMMAND: Partial<Record<RideDetails['status'], { command: DriverRideCommand; label: string }>> = {
  assigned: { command: 'arrive', label: 'Я на месте' },
  arrived: { command: 'start', label: 'Начать поездку' },
  in_progress: { command: 'complete', label: 'Завершить поездку' },
}

function ReleaseForm({ rideId }: { rideId: string }) {
  const release = useReleaseRide(rideId)
  const [reason, setReason] = useState('')
  return (
    <form
      className="grid gap-2"
      onSubmit={(event) => {
        event.preventDefault()
        if (reason.trim()) release.mutate(reason.trim())
      }}
    >
      <Input placeholder="Причина отказа" maxLength={200} value={reason} onChange={(e) => setReason(e.target.value)} />
      <ErrorAlert error={release.error} />
      <Button type="submit" variant="outline" disabled={!reason.trim() || release.isPending}>
        Освободить заказ
      </Button>
    </form>
  )
}

export function ActiveRidePanel({ ride, onDismiss }: { ride: RideDetails; onDismiss: () => void }) {
  const command = useDriverRideCommand(ride.id)
  const next = NEXT_COMMAND[ride.status]
  const releasable = ride.status === 'assigned' || ride.status === 'arrived'

  return (
    <div className="grid gap-3">
      <div className="flex items-center justify-between">
        <RideStatusBadge status={ride.status} />
        <span className="text-lg font-semibold">{formatMoney(ride.amount_kzt)}</span>
      </div>
      <p className="text-sm text-muted-foreground">
        {formatDistance(ride.route.distance_m)} · {formatDuration(ride.route.duration_s)}
      </p>
      {ride.status === 'cancelled' && (
        <>
          <p className="text-sm">Пассажир отменил поездку.</p>
          <Button variant="outline" onClick={onDismiss}>Понятно</Button>
        </>
      )}
      <ErrorAlert error={command.error} />
      {next && (
        <Button size="lg" disabled={command.isPending} onClick={() => command.mutate(next.command)}>
          {next.label}
        </Button>
      )}
      {releasable && <ReleaseForm rideId={ride.id} />}
    </div>
  )
}

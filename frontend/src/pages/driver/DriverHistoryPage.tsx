import { useState } from 'react'
import type { RideSummary } from '@/api'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { RouteTitle } from '@/components/driver/RouteTitle'
import { Screen, ScreenColumn } from '@/components/driver/Screen'
import { Chip, Skeleton, StatusPill } from '@/components/ui-kit'
import { useRideHistory } from '@/hooks/use-rides'
import { formatMoney } from '@/lib/format'
import { formatRideTime, formatSpan, periodStart, ridePill, ridesWord, summarizeShift, type HistoryPeriod } from './shift-stats'

const PERIODS: { id: HistoryPeriod; label: string; earned: string }[] = [
  { id: 'today', label: 'Сегодня', earned: 'Заработано сегодня' },
  { id: 'week', label: 'Неделя', earned: 'Заработано за неделю' },
  { id: 'all', label: 'Все', earned: 'Заработано всего' },
]

const LIMIT = 100

function RideRow({ ride, now }: { ride: RideSummary; now: Date }) {
  const pill = ridePill(ride)
  const method = ride.payment_method === 'kaspi_link' ? 'Kaspi' : 'наличные'
  return (
    <li className="flex w-full items-center gap-3 overflow-hidden p-3">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <p className="truncate text-callout text-text-primary">
          <RouteTitle pickup={ride.pickup} dropoff={ride.dropoff} />
        </p>
        <p className="truncate text-caption text-text-secondary">
          {formatRideTime(ride.created_at, now)} · {method}
        </p>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        <p className="text-callout whitespace-nowrap text-text-primary">{formatMoney(ride.amount_kzt)}</p>
        <StatusPill tone={pill.tone}>{pill.label}</StatusPill>
      </div>
    </li>
  )
}

/** Figma 26:577: earnings and rides for today, the week or all time. */
export function DriverHistoryPage() {
  const [period, setPeriod] = useState<HistoryPeriod>('today')
  const [now] = useState(() => new Date())
  const history = useRideHistory({ created_from: periodStart(period, now), limit: LIMIT })
  const rides = history.data?.items ?? []
  const stats = summarizeShift(rides)
  const current = PERIODS.find((item) => item.id === period) ?? PERIODS[0]

  return (
    <Screen tone="subtle">
      <ScreenColumn className="gap-4 pt-[calc(64px+env(safe-area-inset-top))] pb-6">
        <h1 className="w-full text-display text-text-primary">История</h1>
        <div className="flex w-full flex-col gap-1 overflow-hidden rounded-[20px] bg-bg-inverse p-5 text-text-inverse">
          <p className="text-callout">{current?.earned}</p>
          <p className="text-display">{formatMoney(stats.earnedKzt)}</p>
          <p className="text-caption">
            {stats.rides} {ridesWord(stats.rides)} · {formatSpan(stats.drivingS)} в пути
          </p>
        </div>
        <div className="flex w-full items-center gap-2 overflow-x-auto scrollbar-none">
          {PERIODS.map((item) => (
            <Chip key={item.id} selected={item.id === period} onClick={() => setPeriod(item.id)}>
              {item.label}
            </Chip>
          ))}
        </div>
        <ErrorAlert error={history.error} />
        {history.isPending ? (
          <Skeleton className="h-56 w-full rounded-lg" />
        ) : rides.length === 0 ? (
          <p className="w-full rounded-lg bg-bg-canvas p-5 text-center text-callout text-text-secondary">
            Поездок за этот период нет
          </p>
        ) : (
          <ul className="flex w-full flex-col overflow-hidden rounded-lg bg-bg-canvas p-2">
            {rides.map((ride) => (
              <RideRow key={ride.id} ride={ride} now={now} />
            ))}
          </ul>
        )}
      </ScreenColumn>
    </Screen>
  )
}

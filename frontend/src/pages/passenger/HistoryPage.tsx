import { useState } from 'react'
import { Link } from 'react-router'
import { Receipt } from 'lucide-react'
import { isRideActive, type RideSummary } from '@/api'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { SectionLabel } from '@/components/passenger/layout'
import { usePlaceTitle } from '@/components/passenger/ride-text'
import { Button, Chip, Skeleton, StatusIcon, StatusPill } from '@/components/ui-kit'
import { useRideHistory } from '@/hooks/use-rides'
import { filterStatuses, groupByDay, HISTORY_FILTERS, historyMeta, historyPrice, ridePill, type HistoryFilter } from './model/history'

const PAGE_SIZE = 20

function RideCard({ ride }: { ride: RideSummary }) {
  const title = usePlaceTitle(ride.dropoff)
  const pill = ridePill(ride)
  return (
    <Link
      to={isRideActive(ride.status) ? `/ride/${ride.id}` : `/history/${ride.id}`}
      className="flex w-full flex-col gap-2.5 rounded-lg bg-bg-subtle p-4 outline-none transition-opacity active:opacity-70 focus-visible:ring-2 focus-visible:ring-bg-inverse"
    >
      <span className="flex w-full items-center gap-3 text-body-medium text-text-primary">
        <span className="min-w-0 flex-1 truncate">{title ?? <Skeleton className="inline-block h-4 w-32 align-middle" />}</span>
        <span className="shrink-0 whitespace-nowrap">{historyPrice(ride)}</span>
      </span>
      <span className="flex w-full items-center gap-3">
        <span className="min-w-0 flex-1 truncate text-caption text-text-secondary">{historyMeta(ride)}</span>
        <StatusPill tone={pill.tone}>{pill.text}</StatusPill>
      </span>
    </Link>
  )
}

function EmptyHistory() {
  return (
    <div className="flex w-full flex-col items-center gap-3 pt-[120px] text-center">
      <StatusIcon icon={Receipt} size={80} className="bg-bg-subtle" />
      <h2 className="w-full text-headline text-text-primary">Поездок пока нет</h2>
      <p className="w-full text-callout text-text-secondary">Здесь появятся ваши поездки и чеки</p>
      <Button size="md" asChild>
        <Link to="/">Заказать такси</Link>
      </Button>
    </div>
  )
}

/** Figma History 5:550 and «История пуста» 24:826. */
export function HistoryPage() {
  const [filter, setFilter] = useState<HistoryFilter>('all')
  const [limit, setLimit] = useState(PAGE_SIZE)
  const history = useRideHistory({ status: filterStatuses(filter), limit, offset: 0 })
  const page = history.data
  const empty = page !== undefined && page.total === 0 && filter === 'all'

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 px-4 pt-[64px] pb-6 lg:pt-8">
      <h1 className="w-full text-display text-text-primary">{empty ? 'История' : 'Поездки'}</h1>
      {empty ? (
        <EmptyHistory />
      ) : (
        <>
          <div role="group" aria-label="Фильтр поездок" className="flex w-full items-center gap-2 overflow-x-auto scrollbar-none">
            {HISTORY_FILTERS.map((item) => (
              <Chip
                key={item.id}
                selected={filter === item.id}
                onClick={() => {
                  setFilter(item.id)
                  setLimit(PAGE_SIZE)
                }}
              >
                {item.label}
              </Chip>
            ))}
          </div>
          {history.isPending && [0, 1, 2].map((key) => <Skeleton key={key} className="h-[88px] w-full rounded-lg" />)}
          <ErrorAlert error={history.error} />
          {page && page.items.length === 0 && <p className="text-callout text-text-secondary">Таких поездок нет</p>}
          {page &&
            groupByDay(page.items).map(([label, rides]) => (
              <section key={label} className="flex w-full flex-col gap-4">
                <SectionLabel>{label}</SectionLabel>
                <div className="flex w-full flex-col gap-3">
                  {rides.map((ride) => (
                    <RideCard key={ride.id} ride={ride} />
                  ))}
                </div>
              </section>
            ))}
          {page && page.total > page.items.length && (
            <Button variant="secondary" size="md" loading={history.isFetching} onClick={() => setLimit((value) => value + PAGE_SIZE)}>
              Показать ещё
            </Button>
          )}
        </>
      )}
    </div>
  )
}

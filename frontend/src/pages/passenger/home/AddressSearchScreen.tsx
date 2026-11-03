import { useState } from 'react'
import { ChevronRight, CircleDot, MapPin, Search } from 'lucide-react'
import type { Coordinates } from '@/api'
import { FullScreen, ScreenHeader, SectionLabel } from '@/components/passenger/layout'
import { Input, ListRow, Skeleton } from '@/components/ui-kit'
import { useAddressSearch } from '@/hooks/use-geocoding'
import { MIN_QUERY_LENGTH, type Place } from '@/lib/geocoding'
import { distanceMeters, formatKm } from '@/pages/passenger/model/format'
import type { Target } from './flow'

const PLACEHOLDER: Record<Target, string> = { pickup: 'Откуда', dropoff: 'Куда едем?' }

function StaticField({ icon: Icon, text, onClick }: { icon: typeof Search; text: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-14 w-full shrink-0 items-center gap-3 rounded-md bg-bg-subtle px-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
    >
      <Icon className="size-6 shrink-0 text-text-primary" strokeWidth={2} aria-hidden />
      <span className="min-w-0 flex-1 truncate text-body-medium text-text-secondary">{text}</span>
    </button>
  )
}

function Results({ query, origin, onSelect }: { query: string; origin: Coordinates; onSelect: (place: Place) => void }) {
  const search = useAddressSearch(query)
  if (query.trim().length < MIN_QUERY_LENGTH) return null
  if (search.isFetching && !search.data) {
    return (
      <div className="flex w-full flex-col gap-3" aria-busy>
        {[0, 1, 2].map((key) => (
          <Skeleton key={key} className="h-16 w-full rounded-lg" />
        ))}
      </div>
    )
  }
  if (search.isError) return <p className="text-callout text-text-secondary">Поиск адресов недоступен. Выберите точку на карте.</p>
  const places = search.data ?? []
  if (places.length === 0) return <p className="text-callout text-text-secondary">Ничего не нашлось в Алматы</p>
  return (
    <div className="flex w-full flex-col">
      {places.map((place) => (
        <ListRow
          key={place.id}
          icon={MapPin}
          title={place.title}
          subtitle={[place.subtitle, formatKm(distanceMeters(origin, place.point))].filter(Boolean).join(' · ')}
          onClick={() => onSelect(place)}
        />
      ))}
    </div>
  )
}

/** Figma 23:2 «Поиск адреса»: route fields, «Выбрать на карте» and Nominatim results. */
export function AddressSearchScreen({
  target,
  pickupText,
  dropoffText,
  origin,
  onTargetChange,
  onSelect,
  onPickOnMap,
  onBack,
}: {
  target: Target
  pickupText: string
  dropoffText: string | null
  origin: Coordinates
  onTargetChange: (target: Target) => void
  onSelect: (place: Place) => void
  onPickOnMap: () => void
  onBack: () => void
}) {
  const [query, setQuery] = useState('')
  const field = (
    <Input
      key={target}
      icon={Search}
      autoFocus
      value={query}
      onChange={(event) => setQuery(event.target.value)}
      placeholder={PLACEHOLDER[target]}
      aria-label={target === 'pickup' ? 'Откуда' : 'Куда'}
      enterKeyHint="search"
    />
  )
  return (
    <FullScreen>
      <div className="mx-auto flex w-full max-w-[420px] flex-col gap-4 px-4 pt-[56px] pb-6 lg:pt-8">
        <ScreenHeader title="Маршрут" back={{ onClick: onBack }} />
        <div className="flex w-full flex-col gap-2">
          {target === 'pickup' ? field : <StaticField icon={CircleDot} text={pickupText} onClick={() => onTargetChange('pickup')} />}
          {target === 'dropoff' ? (
            field
          ) : (
            <StaticField icon={MapPin} text={dropoffText ?? 'Куда едем?'} onClick={() => onTargetChange('dropoff')} />
          )}
        </div>
        <button
          type="button"
          onClick={onPickOnMap}
          className="flex w-full items-center gap-3 rounded-md py-1 text-left outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
        >
          <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-bg-muted">
            <MapPin className="size-6 text-text-primary" strokeWidth={2} aria-hidden />
          </span>
          <span className="min-w-0 flex-1 text-body-medium text-text-primary">Выбрать на карте</span>
          <ChevronRight className="size-6 shrink-0 text-text-primary" strokeWidth={2} aria-hidden />
        </button>
        <div className="h-px w-full bg-border-default" />
        {query.trim().length >= MIN_QUERY_LENGTH && <SectionLabel>РЕЗУЛЬТАТЫ</SectionLabel>}
        <Results query={query} origin={origin} onSelect={onSelect} />
        <p className="w-full text-caption text-text-tertiary">Адреса — OpenStreetMap</p>
      </div>
    </FullScreen>
  )
}

import { Clock, MapPin, Search } from 'lucide-react'
import { ListRow } from '@/components/ui-kit'
import type { Place } from '@/lib/geocoding'

/** Figma Home 4:174: «Куда едем?», a search field and suggestions. */
export function HomeSheet({
  places,
  onSearch,
  onPickOnMap,
  onPlace,
}: {
  places: Place[]
  onSearch: () => void
  onPickOnMap: () => void
  onPlace: (place: Place) => void
}) {
  return (
    <>
      <h1 className="w-full text-title text-text-primary">Куда едем?</h1>
      <button
        type="button"
        onClick={onSearch}
        className="flex h-14 w-full shrink-0 items-center gap-3 rounded-md bg-bg-subtle px-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
      >
        <Search className="size-6 shrink-0 text-text-primary" strokeWidth={2} aria-hidden />
        <span className="min-w-0 flex-1 truncate text-body-medium text-text-secondary">Куда едем?</span>
      </button>
      <div className="flex w-full flex-col">
        <ListRow
          icon={MapPin}
          title="Точка на карте"
          subtitle="Коснитесь карты, чтобы выбрать адрес"
          onClick={onPickOnMap}
        />
        {places.map((place) => (
          <ListRow key={place.id} icon={Clock} title={place.title} subtitle={place.subtitle} onClick={() => onPlace(place)} />
        ))}
      </div>
    </>
  )
}

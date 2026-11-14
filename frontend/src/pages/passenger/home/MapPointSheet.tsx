import { t, useLocale } from '@/i18n/core'
import { MapPin } from 'lucide-react'
import { Button, ListRow, Skeleton } from '@/components/ui-kit'
import type { Place } from '@/lib/geocoding'
import type { Target } from './flow'
const MAP_POINT_TITLE = (): Record<Target, string> => ({
  pickup: t('Откуда едем?'),
  dropoff: t('Куда едем?'),
})
/** Figma 23:174: the address under the pin and «Готово». */
export function MapPointSheet({
  target,
  place,
  onDone,
}: {
  target: Target
  place: Place | undefined
  onDone: () => void
}) {
  useLocale()
  return (
    <>
      <h1 className="w-full text-title text-text-primary">{MAP_POINT_TITLE()[target]}</h1>
      <ListRow
        icon={MapPin}
        title={place ? place.title : <Skeleton className="inline-block h-4 w-40 align-middle" />}
        subtitle={place?.subtitle || ' '}
      />
      <p className="w-full text-caption text-text-secondary">
        {t('Двигайте карту, чтобы поставить точку точнее')}
      </p>
      <Button className="w-full" disabled={!place} onClick={onDone}>
        {t('Готово')}
      </Button>
    </>
  )
}

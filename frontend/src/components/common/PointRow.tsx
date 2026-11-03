import { MapPin } from 'lucide-react'
import { cn } from 'cn'
import type { Coordinates } from '@/api'
import { formatCoordinates } from '@/lib/format'

interface PointRowProps {
  label: string
  point: Coordinates | null
  color: string
  active?: boolean
  onSelect?: () => void
}

/** The backend has no geocoding: a point is shown as «Точка на карте» with its coordinates. */
export function PointRow({ label, point, color, active, onSelect }: PointRowProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={!onSelect}
      className={cn(
        'flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left',
        active && 'border-foreground',
      )}
    >
      <MapPin className="size-4 shrink-0" style={{ color }} aria-hidden />
      <span className="grid">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="text-sm">
          {point ? `Точка на карте · ${formatCoordinates(point)}` : 'Нажмите на карту'}
        </span>
      </span>
    </button>
  )
}

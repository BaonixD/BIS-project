import { Phone } from 'lucide-react'
import type { DriverCard } from '@/api'
import { minutesSince } from '@/lib/format'

const STALE_LOCATION_MIN = 2

export function DriverInfo({ driver, now }: { driver: DriverCard; now: number }) {
  const vehicle = driver.vehicle
  const staleMinutes = driver.location_updated_at ? minutesSince(driver.location_updated_at, now) : null
  return (
    <div className="grid gap-1 rounded-lg border p-3">
      <p className="font-medium">{driver.full_name ?? 'Водитель'}</p>
      {vehicle && (
        <p className="text-sm text-muted-foreground">
          {vehicle.color} {vehicle.make} {vehicle.model} · <span className="font-mono">{vehicle.plate_number}</span>
        </p>
      )}
      {driver.phone && (
        <a href={`tel:${driver.phone}`} className="flex items-center gap-2 text-sm underline-offset-4 hover:underline">
          <Phone className="size-4" aria-hidden /> {driver.phone}
        </a>
      )}
      {staleMinutes !== null && staleMinutes >= STALE_LOCATION_MIN && (
        <p className="text-xs text-muted-foreground">Позиция обновлена {staleMinutes} мин назад</p>
      )}
    </div>
  )
}

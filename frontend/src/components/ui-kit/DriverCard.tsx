import { CarIcon, type CarClass } from './CarIcon'
import { cn } from '@/lib/utils'

interface DriverCardProps {
  name: string
  /** «Toyota Camry · серо-синий». */
  vehicle: string
  plate: string
  carClass?: CarClass
  className?: string
}

/** Figma «DriverCard» 5:451: car silhouette, driver name, model and a plate badge. */
export function DriverCard({ name, vehicle, plate, carClass = 'comfort', className }: DriverCardProps) {
  return (
    <div
      data-slot="driver-card"
      className={cn('flex w-full items-center gap-3 overflow-hidden rounded-lg bg-bg-subtle p-4', className)}
    >
      <CarIcon carClass={carClass} className="h-[33.6px] w-[72px]" />
      <div className="flex min-w-0 flex-1 flex-col items-start gap-1">
        <p className="w-full truncate text-headline text-text-primary">{name}</p>
        <p className="w-full truncate text-caption text-text-secondary">{vehicle}</p>
        <span className="rounded-[6px] border-[1.5px] border-solid border-bg-inverse bg-bg-canvas px-2 py-1 text-[12px] leading-4 font-bold tracking-[0.2px] whitespace-nowrap text-text-primary">
          {plate}
        </span>
      </div>
    </div>
  )
}

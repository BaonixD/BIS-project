import type { ReactNode } from 'react'
import { CircleDot, MapPin, type LucideIcon } from 'lucide-react'
import type { Coordinates, DriverCard as DriverCardData } from '@/api'
import type { Tariff } from '@/api/passenger-types'
import { DriverCard, ListRow, Skeleton, StatusIcon, type StatusIconTone } from '@/components/ui-kit'
import { cn } from '@/lib/utils'
import { shortName } from '@/pages/passenger/model/format'
import { usePlaceTitle, vehicleText } from './ride-text'

export function PlaceTitle({ point, className }: { point: Coordinates; className?: string }) {
  const title = usePlaceTitle(point)
  return title ? <>{title}</> : <Skeleton className={cn('inline-block h-4 w-32 align-middle', className)} />
}

/** Pickup ◉ and drop-off pin rows (Figma «Route» 5:345). */
export function RouteRows({
  pickup,
  dropoff,
  pickupSubtitle = 'Откуда',
  dropoffSubtitle = 'Куда',
  trailing,
}: {
  pickup: Coordinates
  dropoff: Coordinates
  pickupSubtitle?: ReactNode
  dropoffSubtitle?: ReactNode
  trailing?: ReactNode
}) {
  return (
    <div className="flex w-full flex-col">
      <ListRow icon={CircleDot} title={<PlaceTitle point={pickup} />} subtitle={pickupSubtitle} />
      <ListRow icon={MapPin} title={<PlaceTitle point={dropoff} />} subtitle={dropoffSubtitle} trailing={trailing} />
    </div>
  )
}

/** Label/value rows of receipts and summaries (Callout). */
export function SummaryRows({ rows, className }: { rows: [string, ReactNode][]; className?: string }) {
  return (
    <dl className={cn('flex w-full flex-col gap-3 text-left text-callout', className)}>
      {rows.map(([label, value]) => (
        <div key={label} className="flex w-full items-center gap-3">
          <dt className="min-w-0 flex-1 text-text-secondary">{label}</dt>
          <dd className="shrink-0 whitespace-nowrap text-text-primary">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

/** 6px track with a black bar (Figma «Progress» 5:343). */
export function ProgressBar({ value, label }: { value: number; label: string }) {
  const percent = Math.round(Math.min(1, Math.max(0, value)) * 100)
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
      className="relative h-1.5 w-full shrink-0 overflow-hidden rounded-[3px] bg-bg-muted"
    >
      <div
        className="absolute inset-y-0 left-0 rounded-[3px] bg-bg-inverse transition-[width] duration-1000 ease-linear"
        style={{ width: `${percent}%` }}
      />
    </div>
  )
}

/** Centered status icon + Title + Callout text (Figma «Heading» of status sheets). */
export function StatusHeading({
  icon,
  tone = 'neutral',
  size = 72,
  iconClassName,
  title,
  text,
  gap = 'gap-[18px]',
}: {
  icon: LucideIcon
  tone?: StatusIconTone
  size?: 64 | 72 | 80
  iconClassName?: string
  title: string
  text?: ReactNode
  gap?: string
}) {
  return (
    <div className={cn('flex w-full flex-col items-center', gap)}>
      <StatusIcon icon={icon} tone={tone} size={size} className={iconClassName} />
      <div className="flex w-full flex-col items-center gap-1.5 text-center">
        <h1 className="w-full text-title text-text-primary">{title}</h1>
        {/* Chrome lays out Inter ~1px wider than Figma: 12px of slack keeps the mockup's line breaks. */}
        {text && <p className="-mx-3 w-[calc(100%+24px)] text-callout text-text-secondary">{text}</p>}
      </div>
    </div>
  )
}

export function RideDriverCard({ driver, tariff }: { driver: DriverCardData; tariff: Tariff }) {
  return (
    <DriverCard
      name={shortName(driver.full_name)}
      vehicle={vehicleText(driver)}
      plate={driver.vehicle?.plate_number ?? '—'}
      carClass={driver.vehicle?.car_class ?? tariff}
    />
  )
}

/** Round 52px action with a caption (Figma «Actions» 5:459). */
export function RoundAction({
  icon: Icon,
  label,
  onClick,
  href,
}: {
  icon: LucideIcon
  label: string
  onClick?: () => void
  href?: string
}) {
  const body = (
    <>
      <span className="flex size-[52px] items-center justify-center rounded-full bg-bg-muted">
        <Icon className="size-6 text-text-primary" strokeWidth={2} aria-hidden />
      </span>
      <span className="text-caption whitespace-nowrap text-text-secondary">{label}</span>
    </>
  )
  const className =
    'flex shrink-0 flex-col items-center gap-1.5 rounded-md outline-none transition-opacity active:opacity-60 focus-visible:ring-2 focus-visible:ring-bg-inverse'
  if (href) {
    return (
      <a href={href} target={href.startsWith('http') ? '_blank' : undefined} rel="noopener noreferrer" className={className}>
        {body}
      </a>
    )
  }
  return (
    <button type="button" onClick={onClick} className={className}>
      {body}
    </button>
  )
}

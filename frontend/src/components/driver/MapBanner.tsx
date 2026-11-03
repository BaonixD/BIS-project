import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

/** Figma NextStep / Banner (6:313, 25:66): 16px radius, 14×16 padding, 24px icon, Body/Medium + Caption. */
export function MapBanner({
  icon: Icon,
  title,
  subtitle,
  tone = 'inverse',
}: {
  icon: LucideIcon
  title: string
  subtitle: string
  tone?: 'inverse' | 'warning'
}) {
  return (
    <div
      role="status"
      className={cn(
        'flex w-full items-center gap-3 overflow-hidden rounded-lg px-4 py-3.5',
        tone === 'inverse' ? 'bg-bg-inverse text-text-inverse' : 'bg-accent-warning text-text-primary',
      )}
    >
      <Icon className="size-6 shrink-0" strokeWidth={2} aria-hidden />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <p className="text-body-medium">{title}</p>
        <p className="text-caption">{subtitle}</p>
      </div>
    </div>
  )
}

/** Figma StatusCard (6:66, 25:213): white pill with a 10px status dot. */
export function OnlinePill({ online }: { online: boolean }) {
  return (
    <div
      role="status"
      className={cn(
        'flex w-fit items-center overflow-hidden rounded-full bg-bg-canvas px-4 py-3 shadow-card',
        online ? 'gap-2.5' : 'gap-3',
      )}
    >
      <span className={cn('size-2.5 shrink-0 rounded-full', online ? 'bg-accent-success' : 'bg-text-tertiary')} />
      <span className="text-callout whitespace-nowrap text-text-primary">{online ? 'Вы на линии' : 'Вы не на линии'}</span>
    </div>
  )
}

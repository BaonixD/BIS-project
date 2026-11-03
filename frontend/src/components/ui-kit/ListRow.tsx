import type { ComponentProps, ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ListRowProps extends Omit<ComponentProps<'button'>, 'title'> {
  icon?: LucideIcon
  /** Custom leading content instead of the icon circle. */
  leading?: ReactNode
  title: ReactNode
  subtitle?: ReactNode
  trailing?: ReactNode
}

/** Figma «ListRow» 3:97: 44px icon circle, title + subtitle, optional trailing value. A button when `onClick` is set. */
export function ListRow({ icon: Icon, leading, title, subtitle, trailing, onClick, className, ...props }: ListRowProps) {
  const content = (
    <>
      {leading ??
        (Icon && (
          <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-bg-muted">
            <Icon className="size-6 text-text-primary" strokeWidth={2} aria-hidden />
          </span>
        ))}
      <span className="flex min-w-0 flex-1 flex-col items-start gap-0.5 text-left">
        <span className="w-full truncate text-body-medium text-text-primary">{title}</span>
        {subtitle && <span className="w-full truncate text-caption text-text-secondary">{subtitle}</span>}
      </span>
      {trailing !== undefined && (
        <span className="shrink-0 text-body-medium whitespace-nowrap text-text-primary">{trailing}</span>
      )}
    </>
  )
  const base = 'flex h-16 w-full items-center gap-3 py-3'
  if (!onClick) {
    return (
      <div data-slot="list-row" className={cn(base, className)}>
        {content}
      </div>
    )
  }
  return (
    <button
      type="button"
      data-slot="list-row"
      onClick={onClick}
      className={cn(
        base,
        'rounded-md outline-none transition-opacity active:opacity-60 focus-visible:ring-2 focus-visible:ring-bg-inverse',
        className,
      )}
      {...props}
    >
      {content}
    </button>
  )
}

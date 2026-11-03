import type { ComponentProps } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

/** Figma «FloatingButton» (4:158): 48px white circle with Elevation/Card over the map. */
export function FloatingIconButton({
  icon: Icon,
  className,
  type = 'button',
  ...props
}: ComponentProps<'button'> & { icon: LucideIcon; 'aria-label': string }) {
  return (
    <button
      type={type}
      data-slot="floating-icon-button"
      className={cn(
        'flex size-12 shrink-0 items-center justify-center rounded-full bg-bg-canvas text-text-primary shadow-card',
        'outline-none transition-opacity active:opacity-70 focus-visible:ring-2 focus-visible:ring-bg-inverse',
        className,
      )}
      {...props}
    >
      <Icon className="size-6" strokeWidth={2} aria-hidden />
    </button>
  )
}

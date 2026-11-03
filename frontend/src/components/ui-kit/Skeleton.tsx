import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

/** Loading placeholder with a soft shimmer; size it with classes (e.g. `h-16 w-full rounded-lg`). */
export function Skeleton({ className, ...props }: ComponentProps<'div'>) {
  return (
    <div
      data-slot="skeleton"
      aria-hidden
      className={cn(
        'animate-shimmer rounded-md bg-[linear-gradient(90deg,var(--color-bg-muted)_25%,var(--color-bg-subtle)_50%,var(--color-bg-muted)_75%)] bg-size-[200%_100%]',
        className,
      )}
      {...props}
    />
  )
}

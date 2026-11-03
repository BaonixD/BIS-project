import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

/** Loading placeholder in bg/muted; size it with classes (e.g. `h-16 w-full rounded-lg`). */
export function Skeleton({ className, ...props }: ComponentProps<'div'>) {
  return (
    <div data-slot="skeleton" aria-hidden className={cn('animate-pulse rounded-md bg-bg-muted', className)} {...props} />
  )
}

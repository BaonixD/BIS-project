import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

/** Figma «Chip» 2:144: filter pill, black when selected. */
export function Chip({
  selected = false,
  className,
  type = 'button',
  ...props
}: ComponentProps<'button'> & { selected?: boolean }) {
  return (
    <button
      type={type}
      data-slot="chip"
      aria-pressed={selected}
      className={cn(
        'inline-flex h-10 shrink-0 items-center rounded-full px-4 text-callout whitespace-nowrap',
        'transition-colors duration-150 outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse focus-visible:ring-offset-2',
        selected ? 'bg-bg-inverse text-text-inverse' : 'bg-bg-muted text-text-primary',
        className,
      )}
      {...props}
    />
  )
}

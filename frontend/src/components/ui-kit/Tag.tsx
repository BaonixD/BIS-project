import type { ComponentProps } from 'react'
import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TagProps extends Omit<ComponentProps<'button'>, 'onChange'> {
  selected?: boolean
  onSelectedChange?: (selected: boolean) => void
}

/** Figma «Tag» 30:126: toggleable feedback tag with a check when selected. */
export function Tag({ selected = false, onSelectedChange, onClick, className, children, ...props }: TagProps) {
  return (
    <button
      type="button"
      data-slot="tag"
      aria-pressed={selected}
      onClick={(event) => {
        onClick?.(event)
        if (!event.defaultPrevented) onSelectedChange?.(!selected)
      }}
      className={cn(
        'inline-flex h-8 shrink-0 items-center rounded-full border-solid text-caption whitespace-nowrap',
        'outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse focus-visible:ring-offset-2',
        selected
          ? 'gap-1.5 border-[1.2px] border-text-primary bg-bg-subtle pr-3 pl-2.5 font-medium text-text-primary'
          : 'border border-border-default bg-bg-canvas px-3 text-text-secondary',
        className,
      )}
      {...props}
    >
      {selected && <Check data-slot="tag-check" className="size-3.5" strokeWidth={2.5} aria-hidden />}
      {children}
    </button>
  )
}

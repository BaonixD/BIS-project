import type { ComponentProps, ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface InputProps extends ComponentProps<'input'> {
  /** Leading 24px icon (Figma: search, user, lock, map-pin…). */
  icon?: LucideIcon
  /** Optional trailing element, e.g. a clear button. */
  trailing?: ReactNode
  invalid?: boolean
  containerClassName?: string
}

/**
 * Figma «Input» 3:96: 56px field, subtle background; Focused — white with a 2px black border.
 * The whole field is a label, so clicking the icon focuses the input.
 */
export function Input({ icon: Icon, trailing, invalid, containerClassName, className, ...props }: InputProps) {
  return (
    <label
      data-slot="input"
      className={cn(
        'flex h-14 w-full cursor-text items-center gap-3 rounded-md bg-bg-subtle px-4 transition-colors duration-150',
        'focus-within:border-2 focus-within:border-solid focus-within:border-bg-inverse focus-within:bg-bg-canvas',
        invalid && 'border-2 border-solid border-accent-danger',
        containerClassName,
      )}
    >
      {Icon && <Icon className="size-6 shrink-0 text-text-primary" strokeWidth={2} aria-hidden />}
      <input
        aria-invalid={invalid || undefined}
        className={cn(
          'h-full min-w-0 flex-1 bg-transparent text-body-medium text-text-primary outline-none',
          'placeholder:text-text-secondary disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        {...props}
      />
      {trailing}
    </label>
  )
}

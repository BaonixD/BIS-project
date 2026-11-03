import type { ComponentProps } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * Figma Input (3:96) as used in driver settings (26:500): values in text/secondary,
 * with an optional fixed prefix such as «Права ·». Focus looks like the kit Input.
 */
export function SettingsField({
  icon: Icon,
  prefix,
  className,
  ...props
}: ComponentProps<'input'> & { icon: LucideIcon; prefix?: string }) {
  return (
    <label
      className={cn(
        'flex h-14 w-full cursor-text items-center gap-3 rounded-md bg-bg-subtle px-4 transition-colors duration-150',
        'focus-within:border-2 focus-within:border-solid focus-within:border-bg-inverse focus-within:bg-bg-canvas',
        className,
      )}
    >
      <Icon className="size-6 shrink-0 text-text-primary" strokeWidth={2} aria-hidden />
      <span className="flex min-w-0 flex-1 items-center text-body-medium text-text-secondary">
        {prefix && <span className="shrink-0 whitespace-pre">{prefix} · </span>}
        <input
          className="h-full min-w-0 flex-1 bg-transparent text-body-medium text-text-secondary outline-none placeholder:text-text-tertiary focus:text-text-primary"
          {...props}
        />
      </span>
    </label>
  )
}

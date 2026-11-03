import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

const SIZE = {
  40: 'size-10 text-callout',
  48: 'size-12 text-callout',
  64: 'size-16 text-headline',
} as const

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  return words
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase())
    .join('')
}

/** Grey circle with initials (Figma Avatar 40/48/64) or a 24px icon. */
export function Avatar({
  name,
  icon: Icon,
  size = 48,
  className,
}: {
  name?: string
  icon?: LucideIcon
  size?: keyof typeof SIZE
  className?: string
}) {
  return (
    <span
      aria-hidden
      className={cn(
        'flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-bg-muted whitespace-nowrap text-text-primary',
        SIZE[size],
        className,
      )}
    >
      {Icon ? <Icon className="size-6" strokeWidth={2} /> : initials(name ?? '')}
    </span>
  )
}

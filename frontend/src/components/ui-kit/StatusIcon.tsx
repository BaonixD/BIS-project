import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

export type StatusIconTone = 'neutral' | 'success' | 'danger' | 'info' | 'inverse'

const TONE_CLASS: Record<StatusIconTone, string> = {
  neutral: 'bg-bg-muted text-text-primary',
  success: 'bg-accent-success text-text-inverse',
  danger: 'bg-accent-danger text-text-inverse',
  info: 'bg-accent-info text-text-inverse',
  inverse: 'bg-bg-inverse text-text-inverse',
}

const SIZE_CLASS = { 64: 'size-16', 72: 'size-18', 80: 'size-20' } as const

/** Figma «StatusIcon» (23:258, 24:622, 24:840): a 64/72/80px circle with a 32px icon. */
export function StatusIcon({
  icon: Icon,
  tone = 'neutral',
  size = 72,
  className,
}: {
  icon: LucideIcon
  tone?: StatusIconTone
  size?: keyof typeof SIZE_CLASS
  className?: string
}) {
  return (
    <span
      data-slot="status-icon"
      data-tone={tone}
      className={cn('flex shrink-0 items-center justify-center rounded-full', SIZE_CLASS[size], TONE_CLASS[tone], className)}
    >
      <Icon className="size-8" strokeWidth={2} aria-hidden />
    </span>
  )
}

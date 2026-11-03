import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

export type StatusTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'inverse'

const TONE_CLASS: Record<StatusTone, string> = {
  neutral: 'bg-bg-muted text-text-primary',
  success: 'bg-accent-success text-text-inverse',
  warning: 'bg-accent-warning text-text-primary',
  danger: 'bg-accent-danger text-text-inverse',
  info: 'bg-accent-info text-text-inverse',
  inverse: 'bg-bg-inverse text-text-inverse',
}

/** Figma «StatusPill» 2:139. */
export function StatusPill({
  tone = 'neutral',
  className,
  ...props
}: ComponentProps<'span'> & { tone?: StatusTone }) {
  return (
    <span
      data-slot="status-pill"
      data-tone={tone}
      className={cn(
        'inline-flex w-fit shrink-0 items-center rounded-full px-2.5 py-1 text-label whitespace-nowrap',
        TONE_CLASS[tone],
        className,
      )}
      {...props}
    />
  )
}

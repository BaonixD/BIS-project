import { useId } from 'react'
import { cn } from '@/lib/utils'

/** Display the supplied emblem directly; its original raster is never redrawn. */
export function BrandMark({ className }: { className?: string }) {
  const clip = useId().replaceAll(':', '')
  return (
    <svg
      viewBox="870 150 980 980"
      className={cn('size-10 shrink-0', className)}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <clipPath id={clip}>
          <circle cx="1360" cy="680" r="440" />
          <rect x="1264" y="176" width="192" height="80" rx="24" />
        </clipPath>
      </defs>
      <image
        href="/brand/tezjet-original.png"
        width="2760"
        height="1800"
        clipPath={`url(#${clip})`}
      />
    </svg>
  )
}

export function BrandLogo({
  className,
  inverse = false,
}: {
  className?: string
  inverse?: boolean
}) {
  return (
    <span className={cn('inline-flex shrink-0 items-center gap-2.5', className)}>
      <BrandMark />
      <span
        className={cn(
          'text-headline whitespace-nowrap',
          inverse ? 'text-text-inverse' : 'text-text-primary',
        )}
      >
        TezJet
      </span>
    </span>
  )
}

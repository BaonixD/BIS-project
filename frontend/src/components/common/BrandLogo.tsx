import { cn } from '@/lib/utils'

/** The round TulparTaxi badge: the emblem on white inside a gold ring. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <img
      src="/brand/tulpar-badge.png"
      alt=""
      aria-hidden="true"
      draggable={false}
      className={cn('block size-10 shrink-0 rounded-full', className)}
    />
  )
}

/** Emblem and wordmark in the logo's colours: «Tulpar» navy (white on dark), «Taxi» gold. */
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
      <span className="sr-only">TulparTaxi</span>
      <span
        aria-hidden="true"
        className="text-headline font-extrabold tracking-tight whitespace-nowrap italic"
      >
        <span className={inverse ? 'text-white' : 'text-[#1b4f8a] dark:text-white'}>Tulpar</span>
        <span className="text-[#f4b400]">Taxi</span>
      </span>
    </span>
  )
}

import { cn } from '@/lib/utils'

// «Қошқар мүйіз» (ram's horn): a curled horn and its mirror image.
const HORN =
  'M0 0C-5-11-21-15-25-27c-3-9 1-19 9-21 8-2 15 3 15 11 0 6-4 10-9 10-4 0-7-3-7-6 0-3 2-5 5-5'
const HORN_DETAIL = 'M-24-19c-5-4-9-9-9-17 0-5 2-9 5-12M-23 0c-6-4-9-9-8-15 5 2 9 6 10 11'

/** A small Kazakh ornament motif in the current text colour. */
export function KazakhMotif({ className }: { className?: string }) {
  return (
    <svg
      viewBox="-37 -52 74 56"
      fill="none"
      stroke="currentColor"
      strokeWidth={3.2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={cn('h-5 w-[26px] shrink-0', className)}
    >
      {[1, -1].map((side) => (
        <g key={side} transform={`scale(${side} 1)`}>
          <path d={HORN} />
          <path d={HORN_DETAIL} />
        </g>
      ))}
    </svg>
  )
}

/** A hairline with the motif in the middle; decorative, hidden from assistive technology. */
export function OrnamentDivider({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn('flex items-center gap-2.5 text-brand-gold', className)}>
      <span className="h-px flex-1 bg-current opacity-60" />
      <KazakhMotif />
      <span className="h-px flex-1 bg-current opacity-60" />
    </div>
  )
}

/** Under a page title: the motif followed by a gold line that fades out. */
export function TitleOrnament({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn('flex items-center gap-2 text-brand-gold', className)}>
      <KazakhMotif />
      <span className="h-px w-28 bg-linear-to-r from-brand-gold to-transparent" />
    </div>
  )
}

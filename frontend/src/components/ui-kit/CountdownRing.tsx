import { cn } from '@/lib/utils'

const SIZE = 72
const STROKE = 6
const RADIUS = (SIZE - STROKE) / 2 - 1
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

/** Figma «Countdown» 6:203: 72px ring, 6px #EEE track, black arc shrinking clockwise from 12 o'clock. */
export function CountdownRing({
  seconds,
  total = 30,
  className,
}: {
  seconds: number
  total?: number
  className?: string
}) {
  const remaining = Math.max(0, Math.min(total, seconds))
  const offset = CIRCUMFERENCE * (1 - remaining / total)
  return (
    <div
      role="timer"
      aria-label={`Осталось ${remaining} с`}
      data-slot="countdown-ring"
      className={cn('relative size-18 shrink-0', className)}
    >
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="-rotate-90" aria-hidden>
        <circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} fill="none" stroke="#EEEEEE" strokeWidth={STROKE} />
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="black"
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-1000 ease-linear"
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-headline text-text-primary tabular-nums">
        {remaining}
      </span>
    </div>
  )
}

import { useId } from 'react'
import { almatyHour } from '@/lib/map-theme'
import { cn } from '@/lib/utils'

export type SkyPhase = 'dawn' | 'day' | 'dusk' | 'night'
type Phase = SkyPhase

const SKY: Record<Phase, { top: string; bottom: string; ridge: string; line: string }> = {
  dawn: { top: '#fde3c4', bottom: '#fff8ec', ridge: '#c9a77a', line: '#8f6f45' },
  day: { top: '#d6eff6', bottom: '#f4fbfc', ridge: '#7fb3c0', line: '#3f7a88' },
  dusk: { top: '#f6c9a8', bottom: '#eadcf0', ridge: '#a98aa8', line: '#6d4f6c' },
  night: { top: '#0f1b20', bottom: '#1d3540', ridge: '#3d5a64', line: '#8fb1bb' },
}

function phaseAt(hour: number): Phase {
  if (hour >= 5 && hour < 8) return 'dawn'
  if (hour >= 8 && hour < 17) return 'day'
  if (hour >= 17 && hour < 20) return 'dusk'
  return 'night'
}

// Заилийский Алатау as seen from the city: a far, higher ridge and a nearer, lower one.
const FAR =
  'M0 78L20 70L38 74L58 58L72 64L90 46L104 56L118 50L134 62L150 54L170 38L184 50L198 44L214 58L232 50L250 62L268 52L286 60L304 48L320 58L340 54L360 62'
const NEAR =
  'M0 92L28 80L46 86L70 70L86 78L108 66L126 76L146 72L170 82L196 68L214 76L240 64L262 76L288 70L310 80L334 74L360 82'
const SNOW = 'M162 44L170 38L178 45M84 51L90 46L96 50M298 52L304 48L310 52'
const STARS: readonly [number, number][] = [
  [40, 18], [92, 12], [140, 24], [214, 14], [262, 26], [318, 16], [190, 30],
]

/** A thin-line Alatau ridge under a sky that follows the time of day in Almaty; decorative. */
export function AlatauScene({ className, phase: fixed }: { className?: string; phase?: SkyPhase }) {
  const id = useId()
  const phase = fixed ?? phaseAt(almatyHour())
  const colors = SKY[phase]
  const sun =
    phase === 'night'
      ? { cx: 300, cy: 24, r: 7, fill: '#e9eef0' }
      : phase === 'day'
        ? { cx: 286, cy: 22, r: 9, fill: '#fec50c' }
        : { cx: phase === 'dawn' ? 70 : 300, cy: 50, r: 11, fill: phase === 'dawn' ? '#fdb94a' : '#f4895a' }
  return (
    <svg
      viewBox="0 0 360 110"
      preserveAspectRatio="xMidYMax slice"
      aria-hidden
      className={cn('block h-28 w-full overflow-hidden rounded-[20px]', className)}
    >
      <defs>
        <linearGradient id={`${id}-sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={colors.top} />
          <stop offset="1" stopColor={colors.bottom} />
        </linearGradient>
      </defs>
      <rect width="360" height="110" fill={`url(#${id}-sky)`} />
      {phase === 'night' &&
        STARS.map(([x, y]) => <circle key={`${x}-${y}`} cx={x} cy={y} r="1" fill="#e9eef0" opacity="0.8" />)}
      <circle {...sun} opacity={phase === 'night' ? 0.9 : 0.85} />
      <path d={`${FAR}V110H0Z`} fill={colors.ridge} opacity="0.18" />
      <path d={FAR} fill="none" stroke={colors.line} strokeWidth="1.2" strokeLinejoin="round" opacity="0.55" />
      <path d={SNOW} fill="none" stroke="#ffffff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" opacity={phase === 'night' ? 0.5 : 0.9} />
      <path d={`${NEAR}V110H0Z`} fill={colors.ridge} opacity="0.3" />
      <path d={NEAR} fill="none" stroke={colors.line} strokeWidth="1.4" strokeLinejoin="round" opacity="0.8" />
    </svg>
  )
}

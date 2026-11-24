import { useId, useState, type ReactNode } from 'react'
import { SlidersHorizontal } from 'lucide-react'
import { t, useLocale } from '@/i18n/core'
import {
  SKY_CHOICES,
  setSkyChoice,
  useSkyChoice,
  useSkyPhase,
  type SkyChoice,
  type SkyPhase,
} from '@/lib/sky'
import { cn } from '@/lib/utils'

type Phase = SkyPhase

const SKY: Record<Phase, { top: string; bottom: string; ridge: string; line: string }> = {
  dawn: { top: '#fde3c4', bottom: '#fff8ec', ridge: '#c9a77a', line: '#8f6f45' },
  day: { top: '#d6eff6', bottom: '#f4fbfc', ridge: '#7fb3c0', line: '#3f7a88' },
  dusk: { top: '#f6c9a8', bottom: '#eadcf0', ridge: '#a98aa8', line: '#6d4f6c' },
  night: { top: '#0f1b20', bottom: '#1d3540', ridge: '#3d5a64', line: '#8fb1bb' },
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
  const chosen = useSkyPhase()
  const phase = fixed ?? chosen
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


const GREETING = (): Record<SkyPhase, string> => ({
  dawn: t('Доброе утро'),
  day: t('Добрый день'),
  dusk: t('Добрый вечер'),
  night: t('Доброй ночи'),
})

const CHOICE_LABEL = (): Record<SkyChoice, string> => ({
  auto: t('Авто'),
  dawn: t('Рассвет'),
  day: t('День'),
  dusk: t('Закат'),
  night: t('Ночь'),
})

/** Pick the banner's sky: auto follows the time in Almaty; kept on this device. */
function SkyPicker() {
  useLocale()
  const choice = useSkyChoice()
  return (
    <div
      role="radiogroup"
      aria-label={t('Небо над Алатау')}
      className="flex gap-1.5 overflow-x-auto scrollbar-none motion-safe:animate-fade-up"
    >
      {SKY_CHOICES.map((option) => (
        <button
          key={option}
          type="button"
          role="radio"
          aria-checked={choice === option}
          onClick={() => setSkyChoice(option)}
          className={cn(
            'flex shrink-0 items-center gap-2 rounded-full border py-1 pr-3 pl-1 text-callout outline-none transition-colors focus-visible:ring-2 focus-visible:ring-bg-inverse',
            choice === option
              ? 'border-brand-sky-ink bg-brand-sky-soft text-brand-sky-ink'
              : 'border-border-default bg-bg-canvas text-text-primary',
          )}
        >
          <span className="h-6 w-9 overflow-hidden rounded-full" aria-hidden>
            {option === 'auto' ? (
              <span className="block size-full bg-linear-to-r from-[#fde3c4] via-[#d6eff6] to-[#1d3540]" />
            ) : (
              <AlatauScene phase={option} className="size-full rounded-full" />
            )}
          </span>
          {CHOICE_LABEL()[option]}
        </button>
      ))}
    </div>
  )
}

/** Profile banner: the Alatau under the chosen (or current) sky with a greeting. */
export function AlatauBanner({ name, children }: { name?: string; children?: ReactNode }) {
  useLocale()
  const phase = useSkyPhase()
  const night = phase === 'night'
  const [editing, setEditing] = useState(false)
  return (
    <div className="flex w-full flex-col gap-2">
      <section className="relative w-full overflow-hidden rounded-[20px]">
        <AlatauScene phase={phase} className="h-32 rounded-[20px]" />
        <button
          type="button"
          aria-label={t('Настроить небо')}
          aria-expanded={editing}
          onClick={() => setEditing((open) => !open)}
          className={cn(
            'absolute top-3 right-3 flex size-9 items-center justify-center rounded-full outline-none backdrop-blur-sm transition-colors focus-visible:ring-2 focus-visible:ring-bg-inverse',
            night ? 'bg-white/15 text-white' : 'bg-white/60 text-[#111]',
          )}
        >
          <SlidersHorizontal className="size-4" aria-hidden />
        </button>
        <div
          className={cn(
            'absolute inset-x-0 top-0 flex flex-col gap-0.5 p-4 pr-14',
            night ? 'text-white' : 'text-[#111]',
          )}
        >
          <p className="text-headline">
            {name ? `${GREETING()[phase]}, ${name}` : GREETING()[phase]}
          </p>
          {children && (
            <p className={cn('text-caption', night ? 'text-white/70' : 'text-black/60')}>
              {children}
            </p>
          )}
        </div>
      </section>
      {editing && <SkyPicker />}
    </div>
  )
}

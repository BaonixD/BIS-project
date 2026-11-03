import { useRef, type KeyboardEvent } from 'react'
import { cn } from '@/lib/utils'

const MAX = 5
const STAR_PATH =
  'M14 3.73333L17.0567 9.91667L23.8817 10.9083L18.9467 15.715L20.1133 22.5167L14 19.3083L7.88667 22.5167L9.05333 15.715L4.11833 10.9083L10.9433 9.91667L14 3.73333Z'

function Star({ filled }: { filled: boolean }) {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden className="block">
      <path
        d={STAR_PATH}
        strokeWidth={1.63333}
        strokeLinejoin="round"
        stroke={filled ? '#111111' : '#C9C9C9'}
        fill={filled ? '#111111' : 'none'}
        className="transition-[fill,stroke] duration-150"
      />
    </svg>
  )
}

interface RatingStarsProps {
  value: number
  onChange?: (value: number) => void
  readOnly?: boolean
  label?: string
  className?: string
}

function nextValue(key: string, value: number): number | null {
  switch (key) {
    case 'ArrowRight':
    case 'ArrowUp':
      return Math.min(MAX, value + 1)
    case 'ArrowLeft':
    case 'ArrowDown':
      return Math.max(1, value - 1)
    case 'Home':
      return 1
    case 'End':
      return MAX
    default:
      return null
  }
}

/** Figma «RatingStars» 30:119: 5 × 28px stars, 6px gap; a radio group operable with the keyboard. */
export function RatingStars({ value, onChange, readOnly = false, label = 'Оценка', className }: RatingStarsProps) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const focusIndex = Math.max(0, value - 1)

  const select = (next: number) => {
    if (readOnly) return
    onChange?.(next)
    refs.current[next - 1]?.focus()
  }

  const onKeyDown = (event: KeyboardEvent) => {
    const next = nextValue(event.key, value)
    if (next === null) return
    event.preventDefault()
    select(next)
  }

  return (
    <div
      role="radiogroup"
      aria-label={label}
      aria-readonly={readOnly || undefined}
      className={cn('flex items-start gap-1.5', className)}
      onKeyDown={onKeyDown}
    >
      {Array.from({ length: MAX }, (_, index) => {
        const star = index + 1
        return (
          <button
            key={star}
            ref={(node) => {
              refs.current[index] = node
            }}
            type="button"
            role="radio"
            aria-checked={value === star}
            aria-label={`${star} из ${MAX}`}
            tabIndex={index === focusIndex ? 0 : -1}
            onClick={() => select(star)}
            className={cn(
              'size-7 shrink-0 rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse',
              readOnly && 'cursor-default',
            )}
          >
            <Star filled={star <= value} />
          </button>
        )
      })}
    </div>
  )
}

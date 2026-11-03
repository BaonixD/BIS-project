import type { CSSProperties, ReactNode } from 'react'
import { Car, Power } from 'lucide-react'
import pulseUrl from '@/assets/driver/pulse.svg'
import { cn } from '@/lib/utils'

/**
 * Driver map screens: full-screen map, a card or banner 56px from the frame top (9px below the
 * mockup status bar), the sheet at the bottom. `immersive` screens (offer, ride) cover the nav.
 */
export function DriverMapLayout({
  map,
  top,
  children,
  immersive = false,
}: {
  map: ReactNode
  top?: ReactNode
  children: ReactNode
  immersive?: boolean
}) {
  return (
    <div
      className={cn(
        'fixed inset-0 isolate lg:top-(--top-bar-height)',
        immersive && 'z-50 [--sheet-offset:0px] lg:z-auto',
      )}
    >
      <div className="absolute inset-0 z-0">{map}</div>
      {top && (
        <div className="pointer-events-none absolute inset-x-4 top-[calc(56px+env(safe-area-inset-top))] z-10 *:pointer-events-auto lg:top-8 lg:right-8 lg:left-auto lg:w-[358px]">
          {top}
        </div>
      )}
      {children}
    </div>
  )
}

/** Places a floating element `gap` px above the measured sheet (mobile); bottom-right of the map at ≥1024px. */
function aboveSheet(sheetHeight: number, gap: number): CSSProperties {
  return { '--above-sheet': `${sheetHeight + gap}px` } as CSSProperties
}

/** Figma GoOnline (6:69) / GoOnline/Disabled (25:74): 96px circle, 4px white ring, 20px above the sheet. */
export function GoOnlineButton({
  sheetHeight,
  disabled,
  loading,
  onClick,
}: {
  sheetHeight: number
  disabled?: boolean
  loading?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      aria-label="Выйти на линию"
      style={aboveSheet(sheetHeight, 20)}
      className={cn(
        'absolute bottom-[calc(var(--sheet-offset)+var(--above-sheet))] left-1/2 z-10 flex size-24 -translate-x-1/2 flex-col items-center justify-center gap-0.5 overflow-hidden rounded-full border-4 border-solid border-bg-canvas',
        'outline-none transition-opacity focus-visible:ring-2 focus-visible:ring-bg-inverse active:opacity-80 disabled:cursor-not-allowed',
        'lg:bottom-8 lg:left-auto lg:right-8 lg:translate-x-0',
        disabled ? 'bg-bg-muted text-text-tertiary' : 'bg-bg-inverse text-text-inverse shadow-card',
        loading && 'opacity-70',
      )}
    >
      <Power className="size-6" strokeWidth={2} aria-hidden />
      <span className="text-label">ВЫЙТИ</span>
    </button>
  )
}

/** Figma Pulse (25:216): the waiting driver — green halos around a black car dot, 27px above the sheet. */
export function SearchingPulse({ sheetHeight }: { sheetHeight: number }) {
  return (
    <div
      aria-hidden
      data-slot="searching-pulse"
      style={aboveSheet(sheetHeight, 27)}
      className="pointer-events-none absolute bottom-[calc(var(--sheet-offset)+var(--above-sheet))] left-1/2 z-10 size-[220px] -translate-x-1/2 lg:top-1/2 lg:bottom-auto lg:left-[calc(50%+216px)] lg:-translate-y-1/2"
    >
      <img src={pulseUrl} alt="" width={220} height={220} className="block size-[220px]" />
      <Car className="absolute top-1/2 left-1/2 size-5 -translate-1/2 text-text-inverse" strokeWidth={2} />
    </div>
  )
}

import type { ComponentProps, ReactNode } from 'react'
import { Link } from 'react-router'
import { ArrowLeft, type LucideIcon } from 'lucide-react'
import { BottomSheet } from '@/components/ui-kit'
import { cn } from '@/lib/utils'

/**
 * A passenger screen over the whole viewport (the ride flow has no bottom nav in Figma).
 * Desktop keeps the black top bar visible.
 */
export function FullScreen({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={cn(
        'fixed inset-0 z-50 overflow-y-auto bg-bg-canvas [--sheet-offset:0px] lg:top-(--top-bar-height)',
        className,
      )}
    >
      {children}
    </div>
  )
}

interface MapLayoutProps {
  map: ReactNode
  mapClassName?: string
  sheet: ReactNode
  /** Floating controls over the map (back button, address chip, toast). */
  overlay?: ReactNode
  /** Cover the bottom nav (ride flow) instead of sitting above it (home). */
  overNav?: boolean
  sheetLabel?: string
  sheetClassName?: string
  centered?: boolean
  dimmed?: boolean
  onSheetHeightChange?: (height: number) => void
}

/** Map with a bottom sheet; at ≥1024px the sheet is the floating left panel of Desktop 7:2. */
export function MapLayout({
  map,
  mapClassName,
  sheet,
  overlay,
  overNav = true,
  sheetLabel = 'Панель заказа',
  sheetClassName,
  centered,
  dimmed,
  onSheetHeightChange,
}: MapLayoutProps) {
  return (
    <div
      className={cn(
        'fixed inset-0 isolate lg:top-(--top-bar-height)',
        overNav && 'z-50 [--sheet-offset:0px]',
      )}
    >
      <div className={cn('absolute inset-0 z-0', mapClassName)}>{map}</div>
      {overlay}
      <BottomSheet
        aria-label={sheetLabel}
        centered={centered}
        dimmed={dimmed}
        onHeightChange={onSheetHeightChange}
        className={sheetClassName}
      >
        {sheet}
      </BottomSheet>
    </div>
  )
}

/** Figma 56px from the frame top = 9px under the 47px status bar of the mockup. */
export const OVERLAY_TOP = 'top-[max(56px,env(safe-area-inset-top))] lg:top-8'

export function MapOverlay({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn('absolute left-4 z-30 flex items-center gap-3 lg:left-[464px]', OVERLAY_TOP, className)}>
      {children}
    </div>
  )
}

const ROUND_BUTTON =
  'flex size-11 shrink-0 items-center justify-center rounded-full text-text-primary outline-none transition-opacity active:opacity-70 focus-visible:ring-2 focus-visible:ring-bg-inverse'

type RoundButtonProps = { icon?: LucideIcon; label: string; elevated?: boolean; className?: string } & (
  | { to: string; onClick?: never }
  | ({ to?: never } & Pick<ComponentProps<'button'>, 'onClick'>)
)

/** Figma «IconButton» 44px: subtle on pages, white with Elevation/Card over the map. */
export function RoundButton({ icon: Icon = ArrowLeft, label, elevated, className, to, onClick }: RoundButtonProps) {
  const classes = cn(ROUND_BUTTON, elevated ? 'bg-bg-canvas shadow-card' : 'bg-bg-subtle', className)
  const icon = <Icon className="size-6" strokeWidth={2} aria-hidden />
  if (to) {
    return (
      <Link to={to} aria-label={label} className={classes}>
        {icon}
      </Link>
    )
  }
  return (
    <button type="button" aria-label={label} onClick={onClick} className={classes}>
      {icon}
    </button>
  )
}

/** Back button + Headline title (Figma «TopBar» of Settings 12:616, Search 23:14, Details 24:720). */
export function ScreenHeader({
  title,
  subtitle,
  trailing,
  back,
}: {
  title: string
  subtitle?: ReactNode
  trailing?: ReactNode
  back: { to: string } | { onClick: () => void }
}) {
  return (
    <div className="flex w-full items-center gap-3">
      {'to' in back ? <RoundButton to={back.to} label="Назад" /> : <RoundButton onClick={back.onClick} label="Назад" />}
      <div className="flex min-w-0 flex-1 flex-col">
        <h1 className="truncate text-headline text-text-primary">{title}</h1>
        {subtitle && <p className="truncate text-caption text-text-secondary">{subtitle}</p>}
      </div>
      {trailing}
    </div>
  )
}

/** Uppercase section label: «РЕЗУЛЬТАТЫ», «ПРОФИЛЬ», «СЕГОДНЯ». */
export function SectionLabel({ children }: { children: ReactNode }) {
  return <p className="w-full text-label text-text-tertiary">{children}</p>
}

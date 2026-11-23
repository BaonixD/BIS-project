import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/**
 * A full page on its own background. `overNav` screens (ride results, settings, admin driver card)
 * cover the bottom nav like the Figma frames without it; the desktop top bar stays visible.
 */
export function Screen({
  children,
  tone = 'canvas',
  overNav = false,
  className,
}: {
  children: ReactNode
  tone?: 'canvas' | 'subtle'
  overNav?: boolean
  className?: string
}) {
  return (
    <div
      className={cn(
        'fixed inset-0 overflow-y-auto lg:top-(--top-bar-height)',
        tone === 'subtle' ? 'bg-bg-subtle' : 'bg-bg-canvas',
        overNav ? 'z-50' : 'pb-(--nav-height) lg:pb-0',
        className,
      )}
    >
      {children}
    </div>
  )
}

/** The 358px mobile column; the mockup's 47px status bar is not part of the page. */
export function ScreenColumn({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('mx-auto flex w-full max-w-[390px] flex-col px-4', className)}>{children}</div>
}

/** A primary action pinned to the bottom of an `overNav` screen (Figma Footer, 16px sides). */
export function ScreenFooter({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('fixed inset-x-0 bottom-0 z-10 flex justify-center px-4 pb-[calc(34px+env(safe-area-inset-bottom))]', className)}>
      <div className="flex w-full max-w-[358px] flex-col items-center gap-3">{children}</div>
    </div>
  )
}

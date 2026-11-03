import type { ReactNode } from 'react'
import { errorMessage } from '@/api'
import { cn } from '@/lib/utils'

/**
 * Auth screens (Figma 4:2, 4:43): a 358px column with 16px margins on white.
 * The mockup's 47px status bar belongs to the phone, so content starts `top − 47px` below the safe area.
 */
export function AuthLayout({ children, top }: { children: ReactNode; top: 'login' | 'register' }) {
  return (
    <div className="min-h-dvh bg-bg-canvas text-text-primary lg:flex lg:items-center lg:justify-center">
      <main
        className={cn(
          'mx-auto flex w-full max-w-[390px] flex-col gap-6 px-4 pb-10 lg:py-16',
          top === 'login' ? 'pt-[calc(96px+env(safe-area-inset-top))]' : 'pt-[calc(64px+env(safe-area-inset-top))]',
        )}
      >
        {children}
      </main>
    </div>
  )
}

export function AuthHeading({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="flex flex-col gap-2">
      <h1 className="text-display text-text-primary">{title}</h1>
      <p className="text-body text-text-secondary">{subtitle}</p>
    </div>
  )
}

export function FormError({ error }: { error: unknown }) {
  if (!error) return null
  return (
    <p role="alert" className="text-caption text-accent-danger">
      {errorMessage(error)}
    </p>
  )
}

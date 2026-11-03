import type { ReactNode } from 'react'
import { ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router'

/** Figma TopBar of D8 / A4: 44px round back button, Headline title, optional trailing pill. */
export function BackHeader({ title, fallback, trailing }: { title: string; fallback: string; trailing?: ReactNode }) {
  const navigate = useNavigate()
  return (
    <div className="flex w-full items-center gap-3">
      <button
        type="button"
        aria-label="Назад"
        onClick={() => (window.history.length > 1 ? navigate(-1) : navigate(fallback))}
        className="flex size-11 shrink-0 items-center justify-center rounded-full bg-bg-subtle text-text-primary outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
      >
        <ArrowLeft className="size-6" strokeWidth={2} aria-hidden />
      </button>
      <h1 className="min-w-0 flex-1 truncate text-headline text-text-primary">{title}</h1>
      {trailing}
    </div>
  )
}

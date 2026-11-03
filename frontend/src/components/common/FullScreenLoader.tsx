import { Car } from 'lucide-react'

/** Pulsing car badge while a screen or its data loads. */
export function FullScreenLoader() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-bg-canvas" aria-busy="true">
      <span className="relative flex size-16 items-center justify-center">
        <span className="absolute inset-0 animate-loader-ring rounded-full bg-bg-inverse" />
        <span className="absolute inset-0 animate-loader-ring rounded-full bg-bg-inverse [animation-delay:0.8s]" />
        <span className="relative flex size-14 items-center justify-center rounded-full bg-bg-inverse">
          <Car className="size-7 text-text-inverse" strokeWidth={2} aria-hidden />
        </span>
      </span>
      <span className="text-callout text-text-secondary">Загрузка…</span>
    </div>
  )
}

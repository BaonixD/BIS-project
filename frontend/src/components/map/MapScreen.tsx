import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** Full-height map page above the bottom nav with a bottom sheet (side panel on ≥ 1024px). */
export function MapScreen({ map, sheet }: { map: ReactNode; sheet: ReactNode }) {
  return (
    <div className="relative h-[calc(100dvh-var(--bottom-nav-height)-env(safe-area-inset-bottom))] lg:h-dvh">
      {map}
      <section
        className={cn(
          'absolute inset-x-0 bottom-0 z-10 max-h-[65%] overflow-y-auto rounded-t-2xl border-t bg-background p-4 shadow-lg',
          'lg:inset-x-auto lg:top-4 lg:bottom-auto lg:left-4 lg:max-h-[calc(100%-2rem)] lg:w-96 lg:rounded-2xl lg:border',
        )}
      >
        {sheet}
      </section>
    </div>
  )
}

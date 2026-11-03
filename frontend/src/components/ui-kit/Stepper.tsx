import { cn } from '@/lib/utils'

/** Figma «Stepper» 6:330: driver ride progress — 4px bars, 6px gaps; reached steps are black. */
export function Stepper({ steps, current, className }: { steps: string[]; current: number; className?: string }) {
  return (
    <ol data-slot="stepper" className={cn('flex w-full items-start gap-1.5', className)}>
      {steps.map((step, index) => {
        const reached = index <= current
        return (
          <li
            key={step}
            aria-current={index === current ? 'step' : undefined}
            className="flex min-w-0 flex-1 flex-col gap-1.5"
          >
            <span
              className={cn(
                'h-1 w-full rounded-[2px] transition-colors duration-300',
                reached ? 'bg-bg-inverse' : 'bg-bg-muted',
              )}
            />
            <span className={cn('truncate text-caption', reached ? 'text-text-primary' : 'text-text-tertiary')}>
              {step}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

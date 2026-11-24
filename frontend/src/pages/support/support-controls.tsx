import type { ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'

export function SupportPage({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-bg-subtle lg:min-h-[calc(100dvh-var(--top-bar-height))]">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 pt-[calc(32px+env(safe-area-inset-top))] pb-8 sm:px-6 lg:py-10">
        {children}
      </div>
    </div>
  )
}

export function SupportSelect({
  label,
  value,
  options,
  onChange,
  disabled,
}: {
  label: string
  value: string
  options: readonly (readonly [string, string])[]
  onChange: (value: string) => void
  disabled?: boolean
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1.5 text-caption text-text-secondary">
      {label}
      <span className="relative block">
        <select
          aria-label={label}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          className="h-11 w-full appearance-none rounded-md border border-border-default bg-bg-canvas pr-10 pl-3 text-callout text-text-primary outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse disabled:opacity-50"
        >
          {options.map(([id, text]) => (
            <option key={id} value={id}>
              {text}
            </option>
          ))}
        </select>
        <ChevronDown
          className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-text-secondary"
          aria-hidden
        />
      </span>
    </label>
  )
}

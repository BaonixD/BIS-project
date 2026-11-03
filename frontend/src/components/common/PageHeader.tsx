import type { ReactNode } from 'react'

export function PageHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <header className="flex items-center justify-between gap-3 pb-4">
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      {action}
    </header>
  )
}

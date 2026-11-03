import type { ReactNode } from 'react'

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="py-10 text-center text-sm text-muted-foreground">{children}</p>
}

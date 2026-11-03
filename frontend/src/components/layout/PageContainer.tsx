import type { ReactNode } from 'react'

/** Padded, width-limited container for list and form screens. */
export function PageContainer({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-2xl px-4 pt-6 pb-6">{children}</div>
}

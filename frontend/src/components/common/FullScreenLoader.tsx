import { LoaderCircle } from 'lucide-react'

export function FullScreenLoader() {
  return (
    <div className="flex min-h-dvh items-center justify-center" aria-busy="true">
      <LoaderCircle className="size-6 animate-spin text-muted-foreground" />
      <span className="sr-only">Загрузка…</span>
    </div>
  )
}

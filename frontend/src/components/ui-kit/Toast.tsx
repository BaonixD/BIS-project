import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { toast as sonnerToast, Toaster as SonnerToaster } from 'sonner'

/** Mount once near the app root. Figma «Toast» 23:350 sits 16px from the sides at the top. */
export function Toaster() {
  return (
    <SonnerToaster
      position="top-center"
      offset={16}
      mobileOffset={16}
      gap={8}
      visibleToasts={3}
      toastOptions={{ unstyled: true }}
    />
  )
}

interface ToastOptions {
  title: string
  description?: ReactNode
  icon?: LucideIcon
  duration?: number
}

function ToastCard({ title, description, icon: Icon }: Omit<ToastOptions, 'duration'>) {
  return (
    <div className="flex w-full items-center gap-3 overflow-hidden rounded-lg bg-bg-inverse px-4 py-3.5 text-text-inverse sm:w-[358px]">
      {Icon && <Icon className="size-6 shrink-0" strokeWidth={2} aria-hidden />}
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <p className="text-callout">{title}</p>
        {description && <p className="text-caption">{description}</p>}
      </div>
    </div>
  )
}

/** Black toast with an optional icon, as in Figma «Водитель отказался от заказа». */
export function showToast({ duration, ...content }: ToastOptions): string | number {
  return sonnerToast.custom(() => <ToastCard {...content} />, { duration })
}

export { ToastCard }

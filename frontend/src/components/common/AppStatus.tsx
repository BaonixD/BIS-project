import { useSyncExternalStore } from 'react'
import { RefreshCw, WifiOff } from 'lucide-react'
import { Button } from '@/components/ui-kit'
import { t, useLocale } from '@/i18n/core'
import { applyUpdate, usePwa } from '@/lib/pwa'
import { router } from '@/routes/router'

/** Screens where a reload would interrupt a ride: the update offer waits until they are left. */
function busyPath(pathname: string): boolean {
  return pathname.startsWith('/ride/') || pathname === '/driver'
}

function usePathname(): string {
  return useSyncExternalStore(
    (listener) => router.subscribe(listener),
    () => router.state.location.pathname,
    () => '/',
  )
}

/** App-wide notices: no connection, and a new version ready to switch to. */
export function AppStatus() {
  useLocale()
  const { online, updateReady } = usePwa()
  const pathname = usePathname()
  return (
    <>
      {!online && (
        <div
          role="status"
          className="pointer-events-none fixed inset-x-0 top-[calc(8px+env(safe-area-inset-top))] z-[70] flex justify-center px-4 lg:top-[calc(var(--top-bar-height)+8px)]"
        >
          <p className="inline-flex items-center gap-2 rounded-full bg-bg-inverse px-4 py-2 text-callout text-text-inverse shadow-card">
            <WifiOff className="size-4" aria-hidden />
            {t('Нет подключения к интернету')}
          </p>
        </div>
      )}
      {updateReady && !busyPath(pathname) && (
        <div
          role="status"
          className="fixed inset-x-0 bottom-[calc(var(--nav-height)+12px)] z-[70] flex justify-center px-4 lg:bottom-6"
        >
          <div className="flex w-full max-w-md items-center gap-3 rounded-2xl bg-bg-canvas p-3 pl-4 shadow-card ring-1 ring-border-default">
            <RefreshCw className="size-5 shrink-0 text-brand-sky-ink" aria-hidden />
            <p className="min-w-0 flex-1 text-callout text-text-primary">
              {t('Доступна новая версия')}
            </p>
            <Button size="md" onClick={applyUpdate}>
              {t('Обновить')}
            </Button>
          </div>
        </div>
      )}
    </>
  )
}

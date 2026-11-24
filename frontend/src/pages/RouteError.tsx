import { isRouteErrorResponse, useRouteError } from 'react-router'
import { RefreshCw, WifiOff } from 'lucide-react'
import { Button } from '@/components/ui-kit'
import { t, useLocale } from '@/i18n/core'

/** A screen's code could not load: offline, or a new release removed the old files. */
function isChunkError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? '')
  return /dynamically imported module|Importing a module script failed|Unable to preload CSS|error loading dynamically imported/i.test(
    message,
  )
}

/** Instead of React Router's developer page: a calm explanation and a way back. */
export function RouteError() {
  useLocale()
  const error = useRouteError()
  const offline = typeof navigator !== 'undefined' && !navigator.onLine
  const title = offline
    ? t('Нет подключения к интернету')
    : isChunkError(error)
      ? t('Приложение обновилось')
      : t('Что-то пошло не так')
  const text = offline
    ? t('Этот экран ещё не сохранён на устройстве. Проверьте сеть и попробуйте снова.')
    : isChunkError(error)
      ? t('Обновите страницу, чтобы открыть новую версию.')
      : isRouteErrorResponse(error)
        ? `${error.status} ${error.statusText}`
        : t('Обновите страницу. Если ошибка повторится, напишите в поддержку.')
  return (
    <div className="flex min-h-dvh items-center justify-center bg-bg-subtle px-4 pt-[env(safe-area-inset-top)]">
      <div className="flex w-full max-w-sm flex-col items-center gap-3 rounded-[24px] bg-bg-canvas p-6 text-center">
        <span className="flex size-14 items-center justify-center rounded-full bg-brand-sky-soft text-brand-sky-ink">
          {offline ? <WifiOff className="size-6" aria-hidden /> : <RefreshCw className="size-6" aria-hidden />}
        </span>
        <h1 className="text-headline text-text-primary">{title}</h1>
        <p className="text-callout text-text-secondary">{text}</p>
        <Button className="mt-2 w-full" onClick={() => window.location.reload()}>
          {t('Обновить страницу')}
        </Button>
        <a href="/" className="text-callout text-text-secondary underline underline-offset-4">
          {t('На главную')}
        </a>
      </div>
    </div>
  )
}

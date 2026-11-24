import { useState } from 'react'
import { Share, X } from 'lucide-react'
import { Button } from '@/components/ui-kit'
import { t, useLocale } from '@/i18n/core'
import { isIosSafari, isStandalone, promptInstall, usePwa } from '@/lib/pwa'

const DISMISSED_KEY = 'tulpar.install-dismissed'

function dismissedBefore(): boolean {
  try {
    return window.localStorage.getItem(DISMISSED_KEY) === '1'
  } catch {
    return false
  }
}

/** «TulparTaxi на телефоне»: Chrome's install button, or the Safari steps on an iPhone. */
export function InstallAppCard() {
  useLocale()
  const { canInstall } = usePwa()
  const [hidden, setHidden] = useState(dismissedBefore)
  const ios = isIosSafari()
  if (hidden || isStandalone() || (!canInstall && !ios)) return null
  const dismiss = () => {
    setHidden(true)
    try {
      window.localStorage.setItem(DISMISSED_KEY, '1')
    } catch {
      /* Storage may be disabled. */
    }
  }
  return (
    <section className="relative flex items-start gap-3 rounded-lg bg-bg-canvas p-4">
      <img src="/icons/icon-192.png" alt="" className="size-12 shrink-0 rounded-full" />
      <div className="flex min-w-0 flex-1 flex-col gap-1 pr-6">
        <p className="text-body-medium text-text-primary">{t('TulparTaxi на телефоне')}</p>
        {canInstall ? (
          <>
            <p className="text-caption text-text-secondary">
              {t('Установите приложение: иконка на экране, запуск без браузера.')}
            </p>
            <Button size="md" className="mt-2 self-start" onClick={() => void promptInstall()}>
              {t('Установить')}
            </Button>
          </>
        ) : (
          <p className="text-caption text-text-secondary">
            {t('В Safari нажмите')}{' '}
            <Share className="inline size-4 align-text-bottom" aria-label={t('Поделиться')} />{' '}
            {t('и выберите «На экран „Домой“».')}
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={dismiss}
        aria-label={t('Скрыть')}
        className="absolute top-2 right-2 flex size-9 items-center justify-center rounded-full text-text-tertiary outline-none hover:bg-bg-muted focus-visible:ring-2 focus-visible:ring-bg-inverse"
      >
        <X className="size-4" aria-hidden />
      </button>
    </section>
  )
}

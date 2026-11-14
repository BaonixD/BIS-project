import { t, useLocale } from '@/i18n/core'
import { Navigation } from 'lucide-react'
import { StatusHeading } from '@/components/passenger/ride-parts'
import { Button } from '@/components/ui-kit'
/** Figma 24:897 «Ошибка маршрута». */
export function RouteErrorSheet({
  text,
  onRetry,
  onEdit,
  retrying,
}: {
  text: string
  onRetry: () => void
  onEdit: () => void
  retrying: boolean
}) {
  useLocale()
  return (
    <>
      <StatusHeading
        icon={Navigation}
        size={64}
        title={t('Не удалось построить маршрут')}
        text={text}
      />
      <Button className="w-full" loading={retrying} onClick={onRetry}>
        {t('Повторить')}
      </Button>
      <Button variant="ghost" size="md" className="w-full" onClick={onEdit}>
        {t('Изменить адрес')}
      </Button>
    </>
  )
}

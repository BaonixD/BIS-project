import { t, useLocale } from '@/i18n/core'
import { Link } from 'react-router'
import { PageContainer } from '@/components/layout/PageContainer'
import { Button } from '@/components/ui/button'
export function NotFoundPage() {
  useLocale()
  return (
    <PageContainer>
      <p className="pb-4 text-lg font-semibold">{t('Страница не найдена')}</p>
      <Button asChild variant="outline">
        <Link to="/">{t('На главную')}</Link>
      </Button>
    </PageContainer>
  )
}

import { Link } from 'react-router'
import { PageContainer } from '@/components/layout/PageContainer'
import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <PageContainer>
      <p className="pb-4 text-lg font-semibold">Страница не найдена</p>
      <Button asChild variant="outline">
        <Link to="/">На главную</Link>
      </Button>
    </PageContainer>
  )
}

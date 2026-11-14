import { t, useLocale } from '@/i18n/core'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
interface PaginationProps {
  offset: number
  limit: number
  total: number
  onChange: (offset: number) => void
}
export function Pagination({ offset, limit, total, onChange }: PaginationProps) {
  useLocale()
  if (total <= limit) return null
  const page = Math.floor(offset / limit) + 1
  const pages = Math.ceil(total / limit)
  return (
    <nav className="flex items-center justify-between pt-4" aria-label={t('Страницы')}>
      <Button
        variant="outline"
        size="sm"
        disabled={offset === 0}
        onClick={() => onChange(Math.max(0, offset - limit))}
      >
        <ChevronLeft />
        {t(' Назад')}
      </Button>
      <span className="text-sm text-muted-foreground">
        {page} / {pages}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={offset + limit >= total}
        onClick={() => onChange(offset + limit)}
      >
        {t('Вперёд ')}
        <ChevronRight />
      </Button>
    </nav>
  )
}

import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Bot, MessageCircle } from 'lucide-react'
import { useSupportTickets } from '@/hooks/use-support'
import { Button, Input, Skeleton, StatusPill } from '@/components/ui-kit'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Pagination } from '@/components/common/Pagination'
import { t, useLocale } from '@/i18n/core'
import { formatDateTime } from '@/lib/format'
import { supportCategory, supportStatus } from './support-labels'
import { SupportSelect } from './support-controls'
import { AdminLayout } from '@/pages/admin/admin-controls'

/** The admin queue; passengers and drivers use SupportChatPage. */
export function SupportListPage() {
  useLocale()
  const base = '/admin/support'
  const [params, setParams] = useSearchParams()
  const offset = Math.max(0, Number(params.get('offset')) || 0)
  const status = params.get('status') || ''
  const category = params.get('category') || ''
  const [search, setSearch] = useState(params.get('q') ?? '')
  const query = useSupportTickets(true, {
    status: status || undefined,
    category: category || undefined,
    q: params.get('q') || undefined,
    offset,
  })
  const change = (key: string, value: string) =>
    setParams((previous) => {
      const next = new URLSearchParams(previous)
      next.delete('offset')
      if (value) next.set(key, value)
      else next.delete(key)
      return next
    })
  return (
    <AdminLayout
      title={t('Поддержка')}
      description={t('Вопросы пользователей и ответы команды. Сверху — обращения с последними сообщениями.')}
      refreshing={query.isFetching}
      onRefresh={() => void query.refetch()}
    >
      <section className="overflow-hidden rounded-xl border border-border-default bg-bg-canvas">
        <div className="flex flex-col gap-4 border-b border-border-default p-4 sm:flex-row sm:flex-wrap sm:items-end sm:p-5">
          <div className="w-full sm:w-48">
            <SupportSelect
              label={t('Статус')}
              value={status}
              onChange={(value) => change('status', value)}
              options={[
                ['', t('Все')],
                ...['open', 'in_progress', 'resolved'].map(
                  (value) => [value, supportStatus(value)] as const,
                ),
              ]}
            />
          </div>
          <div className="w-full sm:w-48">
            <SupportSelect
              label={t('Категория')}
              value={category}
              onChange={(value) => change('category', value)}
              options={[
                ['', t('Все')],
                ...['ride', 'payment', 'documents', 'account', 'other'].map(
                  (value) => [value, supportCategory(value)] as const,
                ),
              ]}
            />
          </div>
          <form
            className="flex w-full min-w-0 gap-2 sm:basis-full"
            onSubmit={(event) => {
              event.preventDefault()
              change('q', search.trim())
            }}
          >
            <Input
              placeholder={t('Поиск по теме или пользователю')}
              aria-label={t('Поиск по теме или пользователю')}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              containerClassName="h-11"
              maxLength={100}
            />
            <Button type="submit" size="md">
              {t('Найти')}
            </Button>
          </form>
        </div>
        {query.error && (
          <div className="p-5">
            <ErrorAlert error={query.error} />
          </div>
        )}
        {query.isPending && (
          <div className="p-5">
            <Skeleton className="h-40 rounded-lg" />
          </div>
        )}
        {query.data?.items.length === 0 && (
          <div className="flex flex-col items-center gap-3 px-6 py-14 text-center sm:py-20">
            <div className="flex size-14 items-center justify-center rounded-full bg-bg-subtle">
              <MessageCircle className="size-7 text-text-secondary" aria-hidden />
            </div>
            <h2 className="text-headline text-text-primary">
              {t(
                status || category || params.get('q') ? 'Ничего не найдено' : 'Обращений пока нет',
              )}
            </h2>
            <p className="max-w-sm text-callout text-text-secondary">
              {t(
                status || category || params.get('q')
                  ? 'Попробуйте другой запрос или измените фильтры.'
                  : 'Здесь появятся обращения пользователей.',
              )}
            </p>
          </div>
        )}
        <ul className="flex flex-col divide-y divide-border-default">
          {query.data?.items.map((ticket) => (
            <li key={ticket.id}>
              <Link
                to={`${base}/${ticket.id}`}
                className="flex min-w-0 flex-col gap-3 p-4 outline-none transition-colors hover:bg-bg-subtle focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-bg-inverse sm:p-5"
              >
                <div className="flex items-center justify-between gap-3">
                  <h2 className="min-w-0 break-words text-body-medium">{ticket.subject}</h2>
                  {ticket.unread_count > 0 && (
                    <StatusPill tone="info">{ticket.unread_count}</StatusPill>
                  )}
                </div>
                <p className="truncate text-callout text-text-secondary">{ticket.last_message}</p>
                <div className="flex flex-wrap items-center justify-between gap-2 text-caption text-text-secondary">
                  <span>
                    {supportCategory(ticket.category)} · {formatDateTime(ticket.updated_at)}
                    {` · @${ticket.owner_name}`}
                  </span>
                  {ticket.ai_available && (
                    <span className="mr-auto inline-flex items-center gap-1">
                      <Bot className="size-3.5" aria-hidden />
                      {t('ИИ-помощник')}
                    </span>
                  )}
                  <StatusPill tone={ticket.status === 'resolved' ? 'success' : 'warning'}>
                    {supportStatus(ticket.status)}
                  </StatusPill>
                </div>
              </Link>
            </li>
          ))}
        </ul>
        {query.data && query.data.total > 20 && (
          <div className="border-t border-border-default px-4 pb-4 sm:px-5 sm:pb-5">
            <Pagination
              offset={offset}
              limit={20}
              total={query.data.total}
              onChange={(value) =>
                setParams((previous) => {
                  const next = new URLSearchParams(previous)
                  next.set('offset', String(value))
                  return next
                })
              }
            />
          </div>
        )}
      </section>
    </AdminLayout>
  )
}

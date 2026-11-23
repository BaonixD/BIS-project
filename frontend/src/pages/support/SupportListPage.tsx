import { useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { MessageCircle, Plus, X } from 'lucide-react'
import { Dialog } from 'radix-ui'
import { useSession } from '@/auth/use-session'
import { useSupportTickets, useSupportAction, type Category } from '@/hooks/use-support'
import { Button, Input, Skeleton, StatusPill } from '@/components/ui-kit'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Pagination } from '@/components/common/Pagination'
import { t, useLocale } from '@/i18n/core'
import { formatDateTime } from '@/lib/format'
import { supportCategory, supportStatus } from './support-labels'
import { SupportPage, SupportSelect } from './support-controls'

export function SupportListPage() {
  useLocale()
  const { user } = useSession()
  const admin = user?.role === 'admin'
  const base = admin ? '/admin/support' : user?.role === 'driver' ? '/driver/support' : '/support'
  const [params, setParams] = useSearchParams()
  const offset = Math.max(0, Number(params.get('offset')) || 0)
  const status = params.get('status') || ''
  const category = params.get('category') || ''
  const [search, setSearch] = useState(params.get('q') ?? '')
  const query = useSupportTickets(admin, {
    status: status || undefined,
    category: admin ? category || undefined : undefined,
    q: admin ? params.get('q') || undefined : undefined,
    offset,
  })
  const navigate = useNavigate()
  const action = useSupportAction()
  const [creating, setCreating] = useState(params.get('new') === '1')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [kind, setKind] = useState<Category>(params.get('ride_id') ? 'ride' : 'other')
  const nonce = useRef(crypto.randomUUID())
  const [retryBody, setRetryBody] = useState('')
  const change = (key: string, value: string) =>
    setParams((previous) => {
      const next = new URLSearchParams(previous)
      next.delete('offset')
      if (value) next.set(key, value)
      else next.delete(key)
      return next
    })
  const close = () => {
    if (!action.isPending) {
      setCreating(false)
      action.reset()
    }
  }
  return (
    <SupportPage>
      <header className="flex flex-col items-start gap-4 sm:flex-row sm:justify-between sm:gap-6">
        <div className="min-w-0 flex-1">
          <h1 className="text-title text-text-primary sm:text-display">{t('Поддержка')}</h1>
          <p className="mt-2 max-w-xl text-callout text-text-secondary">
            {t(
              admin
                ? 'Вопросы пользователей и ответы команды'
                : 'Напишите нам, если что-то пошло не так. Ответ появится здесь.',
            )}
          </p>
        </div>
        {!admin && (
          <Button size="md" className="w-full sm:mt-1 sm:w-auto" onClick={() => setCreating(true)}>
            <Plus />
            {t('Написать')}
          </Button>
        )}
      </header>
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
          {admin && (
            <>
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
            </>
          )}
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
                  : admin
                    ? 'Здесь появятся обращения пользователей.'
                    : 'Создайте обращение — мы ответим в этой переписке.',
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
                    {admin ? ` · @${ticket.owner_name}` : ''}
                    {admin && ticket.support_mode === 'ai' ? ` · ${t('ИИ-помощник')}` : ''}
                  </span>
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
      <Dialog.Root
        open={creating}
        onOpenChange={(open) => {
          if (!open) close()
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
          <Dialog.Content className="fixed top-1/2 left-1/2 z-50 flex max-h-[90dvh] w-[calc(100%-32px)] max-w-lg -translate-x-1/2 -translate-y-1/2 flex-col gap-5 overflow-y-auto rounded-xl bg-bg-canvas p-5 shadow-card sm:p-6">
            <Dialog.Title className="pr-10 text-headline">{t('Новое обращение')}</Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                disabled={action.isPending}
                aria-label={t('Закрыть')}
                className="absolute top-4 right-4 flex size-9 items-center justify-center rounded-full bg-bg-subtle outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
              >
                <X className="size-5" aria-hidden />
              </button>
            </Dialog.Close>
            <Dialog.Description className="text-callout text-text-secondary">
              {t('Опишите проблему. Ответ появится в этой переписке.')}
            </Dialog.Description>
            <form
              className="flex flex-col gap-4"
              onSubmit={(event) => {
                event.preventDefault()
                const fingerprint = JSON.stringify([
                  subject.trim(),
                  body.trim(),
                  kind,
                  params.get('ride_id'),
                ])
                if (retryBody !== fingerprint) {
                  nonce.current = crypto.randomUUID()
                  setRetryBody(fingerprint)
                }
                action.mutate(
                  {
                    type: 'create',
                    body: {
                      client_request_id: nonce.current,
                      subject: subject.trim(),
                      body: body.trim(),
                      category: kind,
                      ride_id: params.get('ride_id') || undefined,
                    },
                  },
                  {
                    onSuccess: (data) => {
                      if ('owner_id' in data) {
                        setCreating(false)
                        setSubject('')
                        setBody('')
                        setRetryBody('')
                        nonce.current = crypto.randomUUID()
                        navigate(`${base}/${data.id}`)
                      }
                    },
                  },
                )
              }}
            >
              <SupportSelect
                label={t('Категория')}
                value={kind}
                onChange={(value) => setKind(value as Category)}
                disabled={action.isPending}
                options={['ride', 'payment', 'documents', 'account', 'other'].map(
                  (value) => [value, supportCategory(value)] as const,
                )}
              />
              <div className="flex flex-col gap-1.5">
                <span className="text-caption text-text-secondary">{t('Тема')}</span>
                <Input
                  placeholder={t('Тема')}
                  disabled={action.isPending}
                  containerClassName="h-11 border border-border-default bg-bg-canvas px-3"
                  className="text-callout"
                  aria-label={t('Тема')}
                  maxLength={120}
                  required
                  value={subject}
                  onChange={(event) => setSubject(event.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="support-request-message"
                  className="text-caption text-text-secondary"
                >
                  {t('Сообщение')}
                </label>
                <textarea
                  id="support-request-message"
                  disabled={action.isPending}
                  aria-label={t('Сообщение')}
                  placeholder={t('Что случилось?')}
                  required
                  maxLength={2000}
                  value={body}
                  onChange={(event) => setBody(event.target.value)}
                  className="min-h-36 w-full resize-y rounded-md border border-border-default bg-bg-canvas p-3 text-callout outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
                />
              </div>
              {params.get('ride_id') && (
                <p className="text-caption text-text-secondary">
                  {t('Обращение связано с поездкой')}
                </p>
              )}
              {!admin && (
                <p className="text-caption text-text-secondary">
                  {t(
                    'На общие вопросы сначала может ответить ИИ-помощник. Сообщения для его ответа обрабатывает Google Gemini — не пишите пароли и данные карты.',
                  )}
                </p>
              )}
              <ErrorAlert error={action.error} />
              <div className="grid grid-cols-2 gap-3 pt-1">
                <Button
                  size="md"
                  type="submit"
                  disabled={!subject.trim() || !body.trim()}
                  loading={action.isPending}
                >
                  {t('Отправить')}
                </Button>
                <Button variant="ghost" size="md" disabled={action.isPending} onClick={close}>
                  {t('Отмена')}
                </Button>
              </div>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </SupportPage>
  )
}

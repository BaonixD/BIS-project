import { ArrowLeft } from 'lucide-react'
import { useHideBottomNav } from '@/components/layout/nav-visibility'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSession } from '@/auth/use-session'
import { request, jsonBody } from '@/api/request'
import {
  useSupportAction,
  useSupportTicket,
  type MessagePage,
  type SupportMessage,
} from '@/hooks/use-support'
import { Button, Skeleton, StatusPill } from '@/components/ui-kit'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { t, useLocale } from '@/i18n/core'
import { formatDateTime } from '@/lib/format'
import { supportStatus } from './support-labels'
import { SupportPage } from './support-controls'

interface Conversation {
  items: SupportMessage[]
  fetchedThrough: number
  hasOlder: boolean
}
const EMPTY: SupportMessage[] = []
function mergeMessages(previous: SupportMessage[], next: SupportMessage[]) {
  const merged = new Map(previous.map((message) => [message.seq, message]))
  next.forEach((message) => merged.set(message.seq, message))
  return [...merged.values()].sort((a, b) => a.seq - b.seq)
}
export function SupportThreadPage() {
  const { ticketId } = useParams()
  return <SupportThread key={ticketId} />
}

function SupportThread() {
  useLocale()
  useHideBottomNav(true)
  const { ticketId = '' } = useParams()
  const { user } = useSession()
  const admin = user?.role === 'admin'
  const ticket = useSupportTicket(ticketId)
  const action = useSupportAction()
  const client = useQueryClient()
  const [body, setBody] = useState('')
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [olderError, setOlderError] = useState<Error | null>(null)
  const [atBottom, setAtBottom] = useState(true)
  const bottom = useRef(true)
  const viewport = useRef<HTMLDivElement>(null)
  const readSeq = useRef(0)
  const pendingRead = useRef(false)
  const nonce = useRef({ body: '', id: crypto.randomUUID() })
  const messageKey = ['support', 'messages', ticketId]
  const query = useQuery({
    queryKey: messageKey,
    queryFn: async (): Promise<Conversation> => {
      const before = client.getQueryData<Conversation>(messageKey)
      const page = await request<MessagePage>(
        `/support/tickets/${ticketId}/messages${before ? `?after_seq=${before.fetchedThrough}` : ''}`,
      )
      const current = client.getQueryData<Conversation>(messageKey)
      return {
        items: mergeMessages(current?.items ?? [], page.items),
        fetchedThrough: page.items.at(-1)?.seq ?? current?.fetchedThrough ?? 0,
        hasOlder: current?.hasOlder ?? page.has_more,
      }
    },
    enabled: Boolean(ticket.data),
    refetchInterval: 5_000,
  })
  const loaded = query.data?.items ?? EMPTY
  const older = query.data?.hasOlder ?? false
  useEffect(() => {
    const element = viewport.current
    if (element && bottom.current) element.scrollTop = element.scrollHeight
  }, [loaded])
  const markRead = () => {
    const seq = query.data?.fetchedThrough ?? 0
    if (document.hidden || !bottom.current || pendingRead.current || seq <= readSeq.current) return
    pendingRead.current = true
    void request(`/support/tickets/${ticketId}/read`, {
      method: 'POST',
      ...jsonBody({ last_read_seq: seq }),
    })
      .then(() => {
        readSeq.current = seq
        void client.invalidateQueries({ queryKey: ['support', 'unread'] })
      })
      .catch(() => undefined)
      .finally(() => {
        pendingRead.current = false
      })
  }
  useEffect(() => {
    markRead()
  })
  useEffect(() => {
    const onVisible = () => {
      if (!document.hidden) markRead()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  })
  const scrollBottom = () => {
    const element = viewport.current
    if (element) element.scrollTop = element.scrollHeight
    bottom.current = true
    setAtBottom(true)
    markRead()
  }
  return (
    <SupportPage>
      <Link
        to={admin ? '/admin/support' : user?.role === 'driver' ? '/driver/support' : '/support'}
        className="-ml-2 inline-flex min-h-11 items-center gap-2 self-start rounded-md px-2 text-callout text-text-secondary outline-none hover:text-text-primary focus-visible:ring-2 focus-visible:ring-bg-inverse"
      >
        <ArrowLeft className="size-4" aria-hidden />
        {t('Все обращения')}
      </Link>
      <ErrorAlert error={ticket.error} />
      {ticket.isPending && <Skeleton className="h-40" />}
      {ticket.data && (
        <>
          <header className="flex flex-col items-start gap-3 sm:flex-row sm:justify-between">
            <h1 className="min-w-0 flex-1 text-title [overflow-wrap:anywhere]">
              {ticket.data.subject}
            </h1>
            <StatusPill tone={ticket.data.status === 'resolved' ? 'success' : 'warning'}>
              {supportStatus(ticket.data.status)}
            </StatusPill>
          </header>
          <div className="flex flex-wrap items-center gap-3 text-caption text-text-secondary">
            <span>@{ticket.data.owner_name}</span>
            {ticket.data.ride_id && (
              <Link
                className="underline"
                to={
                  admin
                    ? `/admin/rides/${ticket.data.ride_id}`
                    : user?.role === 'driver'
                      ? '/driver/history'
                      : `/history/${ticket.data.ride_id}`
                }
              >
                {t('Связанная поездка')}
              </Link>
            )}
            {admin && (
              <Button
                size="md"
                variant="secondary"
                disabled={action.isPending}
                onClick={() =>
                  action.mutate({
                    type: 'status',
                    id: ticketId,
                    status: ticket.data!.status === 'resolved' ? 'in_progress' : 'resolved',
                  })
                }
              >
                {t(ticket.data.status === 'resolved' ? 'Открыть снова' : 'Решить вопрос')}
              </Button>
            )}
          </div>
          <div
            ref={viewport}
            className="flex h-[48dvh] min-h-60 w-full min-w-0 flex-col gap-3 overflow-y-auto overscroll-contain rounded-xl border border-border-default bg-bg-canvas p-4 [scrollbar-gutter:stable] sm:p-5"
            role="log"
            aria-label={t('Переписка')}
            aria-live="polite"
            onScroll={(event) => {
              const element = event.currentTarget
              bottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80
              setAtBottom(bottom.current)
              markRead()
            }}
          >
            {older && (
              <Button
                variant="ghost"
                size="md"
                loading={loadingOlder}
                onClick={() => {
                  const first = loaded[0]?.seq
                  if (!first) return
                  setLoadingOlder(true)
                  setOlderError(null)
                  const element = viewport.current
                  const oldHeight = element?.scrollHeight ?? 0
                  bottom.current = false
                  void request<MessagePage>(
                    `/support/tickets/${ticketId}/messages?before_seq=${first}`,
                  )
                    .then((page) => {
                      client.setQueryData<Conversation>(messageKey, (previous) => ({
                        items: mergeMessages(previous?.items ?? [], page.items),
                        fetchedThrough: previous?.fetchedThrough ?? 0,
                        hasOlder: page.has_more,
                      }))
                      requestAnimationFrame(() => {
                        if (element) element.scrollTop += element.scrollHeight - oldHeight
                      })
                    })
                    .catch((error: Error) => setOlderError(error))
                    .finally(() => setLoadingOlder(false))
                }}
              >
                {t('Ранние сообщения')}
              </Button>
            )}
            <ErrorAlert error={query.error ?? olderError} />
            {query.isPending && <p role="status">{t('Загрузка…')}</p>}
            {loaded.map((message) => (
              <article
                key={message.id}
                className={`flex min-w-0 max-w-[88%] flex-col sm:max-w-[75%] gap-1 rounded-lg px-3 py-2 ${message.author_id === user?.id ? 'self-end bg-bg-inverse text-text-inverse' : 'self-start bg-bg-subtle text-text-primary'}`}
              >
                <p className="text-caption opacity-70">
                  {message.author_role === 'admin' ? t('Поддержка') : message.author_name}
                </p>
                <p className="whitespace-pre-wrap text-callout [overflow-wrap:anywhere]">
                  {message.body}
                </p>
                <time className="text-caption opacity-70" dateTime={message.created_at}>
                  {formatDateTime(message.created_at)}
                </time>
              </article>
            ))}
          </div>
          {!atBottom && (
            <Button variant="secondary" size="md" onClick={scrollBottom}>
              {t('Новые сообщения')}
            </Button>
          )}
          <form
            className="flex flex-col gap-3 rounded-xl border border-border-default bg-bg-canvas p-4 sm:p-5"
            onSubmit={(event) => {
              event.preventDefault()
              const text = body.trim()
              if (!text) return
              if (nonce.current.body !== text)
                nonce.current = { body: text, id: crypto.randomUUID() }
              action.mutate(
                {
                  type: 'send',
                  id: ticketId,
                  body: { body: text, client_message_id: nonce.current.id },
                },
                {
                  onSuccess: (data) => {
                    if ('seq' in data)
                      client.setQueryData<Conversation>(messageKey, (previous) => ({
                        items: mergeMessages(previous?.items ?? [], [data]),
                        fetchedThrough: previous?.fetchedThrough ?? 0,
                        hasOlder: previous?.hasOlder ?? false,
                      }))
                    setBody('')
                    nonce.current = { body: '', id: crypto.randomUUID() }
                    bottom.current = true
                  },
                },
              )
            }}
          >
            <label className="sr-only" htmlFor="support-message">
              {t('Сообщение')}
            </label>
            <textarea
              id="support-message"
              disabled={action.isPending}
              required
              maxLength={2000}
              placeholder={t('Ваш ответ')}
              value={body}
              onChange={(event) => setBody(event.target.value)}
              className="min-h-28 w-full resize-y rounded-md border border-border-default bg-bg-subtle p-3 text-callout outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
            />
            <ErrorAlert error={action.error} />
            <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-end">
              {ticket.data.status === 'resolved' && (
                <p className="mr-auto max-w-sm text-caption text-text-secondary">
                  {t('Новое сообщение откроет решённый вопрос снова.')}
                </p>
              )}
              <Button type="submit" size="md" loading={action.isPending} disabled={!body.trim()}>
                {t('Отправить')}
              </Button>
            </div>
          </form>
        </>
      )}
    </SupportPage>
  )
}

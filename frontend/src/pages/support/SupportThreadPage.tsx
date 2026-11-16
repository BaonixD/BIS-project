import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSession } from '@/auth/use-session'
import { request, jsonBody } from '@/api/request'
import { useSupportAction, useSupportTicket, type MessagePage, type SupportMessage } from '@/hooks/use-support'
import { Button, Skeleton, StatusPill } from '@/components/ui-kit'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { t, useLocale } from '@/i18n/core'
import { formatDateTime } from '@/lib/format'
import { supportStatus } from './support-labels'

export function SupportThreadPage() {
  useLocale()
  const { ticketId = '' } = useParams()
  const { user } = useSession()
  const admin = user?.role === 'admin'
  const ticket = useSupportTicket(ticketId)
  const action = useSupportAction()
  const client = useQueryClient()
  const [body, setBody] = useState('')
  const [loaded, setLoaded] = useState<SupportMessage[]>([])
  const [older, setOlder] = useState(false)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [olderError, setOlderError] = useState<Error | null>(null)
  const bottom = useRef(true)
  const viewport = useRef<HTMLDivElement>(null)
  const readSeq = useRef(0)
  const pendingRead = useRef(false)
  const nonce = useRef({ body: '', id: crypto.randomUUID() })
  const latest = loaded.at(-1)?.seq
  const query = useQuery({ queryKey: ['support', 'messages', ticketId, latest ?? 'latest'], queryFn: () => request<MessagePage>(`/support/tickets/${ticketId}/messages${latest === undefined ? '' : `?after_seq=${latest}`}`), enabled: Boolean(ticket.data), refetchInterval: 5_000 })
  useEffect(() => {
    if (!query.data) return
    if (latest === undefined) setOlder(query.data.has_more)
    setLoaded((previous) => {
      const merged = new Map(previous.map((message) => [message.seq, message]))
      query.data.items.forEach((message) => merged.set(message.seq, message))
      const next = [...merged.values()].sort((a, b) => a.seq - b.seq)
      return next.length === previous.length && next.every((message, i) => message.id === previous[i]?.id) ? previous : next
    })
  }, [query.data, latest])
  useEffect(() => {
    const element = viewport.current
    if (element && bottom.current) element.scrollTop = element.scrollHeight
  }, [loaded])
  const markRead = () => {
    const seq = loaded.at(-1)?.seq ?? 0
    if (document.hidden || !bottom.current || pendingRead.current || seq <= readSeq.current) return
    pendingRead.current = true
    void request(`/support/tickets/${ticketId}/read`, { method: 'POST', ...jsonBody({ last_read_seq: seq }) }).then(() => { readSeq.current = seq; void client.invalidateQueries({ queryKey: ['support', 'unread'] }) }).catch(() => undefined).finally(() => { pendingRead.current = false })
  }
  useEffect(() => { markRead() })
  useEffect(() => { const onVisible = () => { if (!document.hidden) markRead() }; document.addEventListener('visibilitychange', onVisible); return () => document.removeEventListener('visibilitychange', onVisible) })
  const scrollBottom = () => { const element = viewport.current; if (element) element.scrollTop = element.scrollHeight; bottom.current = true; markRead() }
  return <div className="min-h-dvh bg-bg-subtle"><div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 pt-[calc(64px+env(safe-area-inset-top))] pb-6 lg:pt-8"><Link to={admin ? '/admin/support' : '/support'} className="text-callout underline">{t('Все обращения')}</Link><ErrorAlert error={ticket.error} />{ticket.isPending && <Skeleton className="h-40" />}
    {ticket.data && <><header className="flex flex-wrap items-center justify-between gap-3"><h1 className="min-w-0 break-words text-title">{ticket.data.subject}</h1><StatusPill tone={ticket.data.status === 'resolved' ? 'success' : 'warning'}>{supportStatus(ticket.data.status)}</StatusPill></header><div className="flex flex-wrap items-center gap-3 text-caption text-text-secondary"><span>@{ticket.data.owner_name}</span>{ticket.data.ride_id && <Link className="underline" to={admin ? `/admin/rides/${ticket.data.ride_id}` : user?.role === 'driver' ? '/driver/history' : `/history/${ticket.data.ride_id}`}>{t('Связанная поездка')}</Link>}{admin && <Button size="md" variant="secondary" disabled={action.isPending} onClick={() => action.mutate({ type: 'status', id: ticketId, status: ticket.data!.status === 'resolved' ? 'in_progress' : 'resolved' })}>{t(ticket.data.status === 'resolved' ? 'Открыть снова' : 'Решить вопрос')}</Button>}</div>
      <div ref={viewport} className="flex h-[48dvh] min-h-56 flex-col gap-3 overflow-y-auto overscroll-contain rounded-lg bg-bg-canvas p-4" role="log" aria-label={t('Переписка')} aria-live="polite" onScroll={(event) => { const element = event.currentTarget; bottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80; markRead() }}>
        {older && <Button variant="ghost" size="md" loading={loadingOlder} onClick={() => { const first = loaded[0]?.seq; if (!first) return; setLoadingOlder(true); setOlderError(null); const element = viewport.current; const oldHeight = element?.scrollHeight ?? 0; bottom.current = false; void request<MessagePage>(`/support/tickets/${ticketId}/messages?before_seq=${first}`).then((page) => { setLoaded((previous) => [...page.items, ...previous]); setOlder(page.has_more); requestAnimationFrame(() => { if (element) element.scrollTop += element.scrollHeight - oldHeight }) }).catch((error: Error) => setOlderError(error)).finally(() => setLoadingOlder(false)) }}>{t('Ранние сообщения')}</Button>}
        <ErrorAlert error={query.error ?? olderError} />{query.isPending && <p role="status">{t('Загрузка…')}</p>}{loaded.map((message) => <article key={message.id} className={`flex max-w-[90%] flex-col gap-1 rounded-lg px-3 py-2 ${message.author_id === user?.id ? 'self-end bg-bg-inverse text-text-inverse' : 'self-start bg-bg-subtle text-text-primary'}`}><p className="text-caption opacity-70">{message.author_role === 'admin' ? t('Поддержка') : message.author_name}</p><p className="whitespace-pre-wrap break-words text-callout">{message.body}</p><time className="text-caption opacity-70" dateTime={message.created_at}>{formatDateTime(message.created_at)}</time></article>)}
      </div>
      {!bottom.current && <Button variant="secondary" size="md" onClick={scrollBottom}>{t('Новые сообщения')}</Button>}
      <form className="flex flex-col gap-2" onSubmit={(event) => { event.preventDefault(); const text = body.trim(); if (!text) return; if (nonce.current.body !== text) nonce.current = { body: text, id: crypto.randomUUID() }; action.mutate({ type: 'send', id: ticketId, body: { body: text, client_message_id: nonce.current.id } }, { onSuccess: (data) => { if ('seq' in data) setLoaded((previous) => [...previous.filter((item) => item.id !== data.id), data].sort((a, b) => a.seq - b.seq)); setBody(''); nonce.current = { body: '', id: crypto.randomUUID() }; bottom.current = true } }) }}><label className="sr-only" htmlFor="support-message">{t('Сообщение')}</label><textarea id="support-message" required maxLength={2000} placeholder={t('Ваш ответ')} value={body} onChange={(event) => setBody(event.target.value)} className="min-h-24 resize-y rounded-md border border-border-default bg-bg-canvas p-3" /><ErrorAlert error={action.error} /><div className="flex items-center justify-between gap-2"><p className="text-caption text-text-secondary">{t('Новое сообщение откроет решённый вопрос снова.')}</p><Button type="submit" size="md" loading={action.isPending} disabled={!body.trim()}>{t('Отправить')}</Button></div></form>
    </>}
  </div></div>
}

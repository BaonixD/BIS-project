import { useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { MessageCircle, Plus } from 'lucide-react'
import { Dialog } from 'radix-ui'
import { useSession } from '@/auth/use-session'
import { useSupportTickets, useSupportAction, type Category } from '@/hooks/use-support'
import { Button, Input, Skeleton, StatusPill } from '@/components/ui-kit'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Pagination } from '@/components/common/Pagination'
import { t, useLocale } from '@/i18n/core'
import { formatDateTime } from '@/lib/format'
import { supportCategory, supportStatus } from './support-labels'

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
  const query = useSupportTickets(admin, { status: status || undefined, category: admin ? category || undefined : undefined, q: admin ? params.get('q') || undefined : undefined, offset })
  const navigate = useNavigate()
  const action = useSupportAction()
  const [creating, setCreating] = useState(params.get('new') === '1')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [kind, setKind] = useState<Category>(params.get('ride_id') ? 'ride' : 'other')
  const nonce = useRef(crypto.randomUUID())
  const [retryBody, setRetryBody] = useState('')
  const change = (key: string, value: string) => setParams((previous) => { const next = new URLSearchParams(previous); next.delete('offset'); value ? next.set(key, value) : next.delete(key); return next })
  const close = () => { if (!action.isPending) { setCreating(false); action.reset() } }
  return <div className="min-h-dvh bg-bg-subtle"><div className="mx-auto flex max-w-4xl flex-col gap-5 px-4 pt-[calc(64px+env(safe-area-inset-top))] pb-8 lg:px-8 lg:pt-8"><header className="flex items-center justify-between gap-3"><div><h1 className="text-display">{t('Поддержка')}</h1><p className="mt-1 text-callout text-text-secondary">{t(admin ? 'Вопросы пользователей и ответы команды' : 'Напишите нам, если что-то пошло не так. Ответ появится здесь.')}</p></div>{!admin && <Button size="md" onClick={() => setCreating(true)}><Plus />{t('Написать')}</Button>}</header>
    <div className="flex flex-wrap items-end gap-3"><label className="flex flex-col gap-1 text-caption">{t('Статус')}<select aria-label={t('Статус')} value={status} onChange={(event) => change('status', event.target.value)} className="h-11 rounded-md border border-border-default bg-bg-canvas px-3"><option value="">{t('Все')}</option>{['open', 'in_progress', 'resolved'].map((value) => <option key={value} value={value}>{supportStatus(value)}</option>)}</select></label>{admin && <><label className="flex flex-col gap-1 text-caption">{t('Категория')}<select value={category} onChange={(event) => change('category', event.target.value)} className="h-11 rounded-md border border-border-default bg-bg-canvas px-3"><option value="">{t('Все')}</option>{['ride', 'payment', 'documents', 'account', 'other'].map((value) => <option key={value} value={value}>{supportCategory(value)}</option>)}</select></label><form className="flex flex-1 gap-2" onSubmit={(event) => { event.preventDefault(); change('q', search.trim()) }}><Input placeholder={t('Поиск по теме или пользователю')} aria-label={t('Поиск по теме или пользователю')} value={search} onChange={(event) => setSearch(event.target.value)} containerClassName="h-11" maxLength={100} /><Button type="submit" size="md">{t('Найти')}</Button></form></>}</div>
    <ErrorAlert error={query.error} />{query.isPending && <Skeleton className="h-40" />}{query.data?.items.length === 0 && <div className="rounded-lg bg-bg-canvas p-8 text-center"><MessageCircle className="mx-auto mb-3 size-8 text-text-tertiary" /><p>{t('Обращений пока нет')}</p></div>}
    <ul className="flex flex-col gap-3">{query.data?.items.map((ticket) => <li key={ticket.id}><Link to={`${base}/${ticket.id}`} className="flex flex-col gap-2 rounded-lg bg-bg-canvas p-4 outline-none hover:shadow-card focus-visible:ring-2"><div className="flex items-center justify-between gap-3"><h2 className="min-w-0 break-words text-body-medium">{ticket.subject}</h2>{ticket.unread_count > 0 && <StatusPill tone="info">{ticket.unread_count}</StatusPill>}</div><p className="truncate text-callout text-text-secondary">{ticket.last_message}</p><div className="flex flex-wrap items-center justify-between gap-2 text-caption text-text-secondary"><span>{supportCategory(ticket.category)} · {formatDateTime(ticket.updated_at)}{admin ? ` · @${ticket.owner_name}` : ''}</span><StatusPill tone={ticket.status === 'resolved' ? 'success' : 'warning'}>{supportStatus(ticket.status)}</StatusPill></div></Link></li>)}</ul>
    {query.data && <Pagination offset={offset} limit={20} total={query.data.total} onChange={(value) => setParams((previous) => { const next = new URLSearchParams(previous); next.set('offset', String(value)); return next })} />}
    <Dialog.Root open={creating} onOpenChange={(open) => { if (!open) close() }}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" /><Dialog.Content className="fixed top-1/2 left-1/2 z-50 flex max-h-[90dvh] w-[calc(100%-32px)] max-w-lg -translate-x-1/2 -translate-y-1/2 flex-col gap-4 overflow-y-auto rounded-xl bg-bg-canvas p-5"><Dialog.Title className="text-headline">{t('Новое обращение')}</Dialog.Title><Dialog.Description className="text-callout text-text-secondary">{t('Опишите проблему. Ответ появится в этой переписке.')}</Dialog.Description><form className="flex flex-col gap-3" onSubmit={(event) => { event.preventDefault(); const fingerprint = JSON.stringify([subject.trim(), body.trim(), kind, params.get('ride_id')]); if (retryBody !== fingerprint) { nonce.current = crypto.randomUUID(); setRetryBody(fingerprint) }; action.mutate({ type: 'create', body: { client_request_id: nonce.current, subject: subject.trim(), body: body.trim(), category: kind, ride_id: params.get('ride_id') || undefined } }, { onSuccess: (data) => { if ('owner_id' in data) { setCreating(false); setSubject(''); setBody(''); setRetryBody(''); nonce.current = crypto.randomUUID(); navigate(`${base}/${data.id}`) } } }) }}><label className="text-caption">{t('Категория')}<select className="mt-1 h-11 w-full rounded-md border border-border-default bg-bg-canvas px-3" value={kind} onChange={(event) => setKind(event.target.value as Category)}>{['ride', 'payment', 'documents', 'account', 'other'].map((value) => <option key={value} value={value}>{supportCategory(value)}</option>)}</select></label><Input placeholder={t('Тема')} aria-label={t('Тема')} maxLength={120} required value={subject} onChange={(event) => setSubject(event.target.value)} /><textarea aria-label={t('Сообщение')} placeholder={t('Что случилось?')} required maxLength={2000} value={body} onChange={(event) => setBody(event.target.value)} className="min-h-32 rounded-md border border-border-default p-3" />{params.get('ride_id') && <p className="text-caption text-text-secondary">{t('Обращение связано с поездкой')}</p>}<ErrorAlert error={action.error} /><Button type="submit" disabled={!subject.trim() || !body.trim()} loading={action.isPending}>{t('Отправить')}</Button><Button variant="ghost" size="md" disabled={action.isPending} onClick={close}>{t('Отмена')}</Button></form></Dialog.Content></Dialog.Portal></Dialog.Root>
  </div></div>
}

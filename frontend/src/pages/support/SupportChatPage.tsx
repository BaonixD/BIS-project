import { useRef, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Bot, Headset, Menu, SquarePen, X } from 'lucide-react'
import { Dialog } from 'radix-ui'
import { useSession } from '@/auth/use-session'
import { useHideBottomNav } from '@/components/layout/nav-visibility'
import {
  useSupportAction,
  useSupportAssistant,
  useSupportTicket,
  useSupportTickets,
  type SupportMessage,
  type Ticket,
} from '@/hooks/use-support'
import { Button, Skeleton } from '@/components/ui-kit'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { OrnamentDivider } from '@/components/common/Ornament'
import { t, useLocale } from '@/i18n/core'
import { ChatLog, Composer, MessageRow, TicketConversation, TypingIndicator } from './chat'
import { conversationKey, subjectFrom, type Conversation } from './chat-model'

const PASSENGER_PROMPTS = [
  'Сколько стоит поездка?',
  'Как оплатить через Kaspi?',
  'Как отменить заказ?',
  'Как оценить поездку?',
]
const DRIVER_PROMPTS = [
  'Какие документы нужны водителю?',
  'Как выйти на линию?',
  'Как сменить класс машины?',
  'Как подтвердить оплату наличными?',
]
const AI_FOOTER = 'ИИ-помощник может ошибаться. Сообщения обрабатывает Google Gemini.'

export function SupportChatPage() {
  useLocale()
  useHideBottomNav(true)
  const { ticketId } = useParams()
  const [params] = useSearchParams()
  const rideId = params.get('ride_id')
  const { user } = useSession()
  const driver = user?.role === 'driver'
  const base = driver ? '/driver/support' : '/support'
  const profile = driver ? '/driver/profile' : '/profile'
  const [drawer, setDrawer] = useState(false)
  const list = (
    <ChatList base={base} activeId={ticketId} onNavigate={() => setDrawer(false)} />
  )
  const openList = () => setDrawer(true)
  return (
    <div className="flex h-dvh bg-bg-canvas lg:h-[calc(100dvh-var(--top-bar-height))]">
      <aside className="hidden w-72 shrink-0 flex-col border-r border-border-default bg-bg-subtle lg:flex">
        {list}
      </aside>
      <main className="flex min-w-0 flex-1 flex-col">
        {ticketId ? (
          <TicketChat key={ticketId} ticketId={ticketId} base={base} onOpenList={openList} />
        ) : (
          <NewChat
            key={rideId ?? 'new'}
            base={base}
            rideId={rideId}
            driver={driver}
            onOpenList={openList}
          />
        )}
      </main>
      <Dialog.Root open={drawer} onOpenChange={setDrawer}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40 lg:hidden" />
          <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-[min(320px,85vw)] flex-col bg-bg-subtle pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] shadow-card outline-none lg:hidden">
            <Dialog.Title className="sr-only">{t('Чаты поддержки')}</Dialog.Title>
            <Dialog.Description className="sr-only">
              {t('Выберите чат или начните новый')}
            </Dialog.Description>
            <div className="flex items-center justify-between px-3 pt-3">
              <Link
                to={profile}
                className="inline-flex min-h-11 items-center gap-2 rounded-lg px-2 text-callout text-text-secondary outline-none hover:text-text-primary focus-visible:ring-2 focus-visible:ring-bg-inverse"
              >
                <ArrowLeft className="size-4" aria-hidden />
                {t('Профиль')}
              </Link>
              <Dialog.Close asChild>
                <button
                  type="button"
                  aria-label={t('Закрыть')}
                  className="flex size-10 items-center justify-center rounded-full outline-none hover:bg-bg-muted focus-visible:ring-2 focus-visible:ring-bg-inverse"
                >
                  <X className="size-5" aria-hidden />
                </button>
              </Dialog.Close>
            </div>
            {list}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  )
}

function ChatList({
  base,
  activeId,
  onNavigate,
}: {
  base: string
  activeId?: string
  onNavigate: () => void
}) {
  const tickets = useSupportTickets(false, {}, 50)
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="p-3">
        <Link
          to={base}
          onClick={onNavigate}
          className="flex h-11 items-center gap-3 rounded-xl px-3 text-callout font-medium outline-none hover:bg-bg-muted focus-visible:ring-2 focus-visible:ring-bg-inverse"
        >
          <SquarePen className="size-5" aria-hidden />
          {t('Новый чат')}
        </Link>
      </div>
      <p className="px-6 pb-2 text-caption text-text-tertiary">{t('Чаты')}</p>
      <nav aria-label={t('Чаты поддержки')} className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        <ErrorAlert error={tickets.error} />
        {tickets.isPending && (
          <div className="flex flex-col gap-2 px-3">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        )}
        {tickets.data?.items.length === 0 && (
          <p className="px-3 py-2 text-caption text-text-tertiary">
            {t('Здесь появятся ваши чаты с поддержкой.')}
          </p>
        )}
        <ul className="flex flex-col gap-0.5">
          {tickets.data?.items.map((ticket) => (
            <li key={ticket.id}>
              <Link
                to={`${base}/${ticket.id}`}
                onClick={onNavigate}
                aria-current={ticket.id === activeId ? 'page' : undefined}
                className={`flex min-w-0 items-center gap-2 rounded-xl px-3 py-2.5 outline-none hover:bg-bg-muted focus-visible:ring-2 focus-visible:ring-bg-inverse ${ticket.id === activeId ? 'bg-brand-sky-soft' : ''}`}
              >
                <span className="flex min-w-0 flex-1 flex-col">
                  <span
                    className={`truncate text-callout ${ticket.status === 'resolved' ? 'text-text-secondary' : ''}`}
                  >
                    {ticket.subject}
                  </span>
                  <span className="truncate text-caption text-text-tertiary">
                    {ticket.last_message}
                  </span>
                </span>
                {ticket.unread_count > 0 && (
                  <span
                    className="size-2.5 shrink-0 rounded-full bg-brand-sky-ink"
                    aria-label={t('Есть новые сообщения')}
                  />
                )}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}

function ChatHeader({
  title,
  subtitle,
  actions,
  base,
  onOpenList,
}: {
  title: string
  subtitle?: ReactNode
  actions?: ReactNode
  base: string
  onOpenList: () => void
}) {
  return (
    <header className="flex min-h-14 shrink-0 items-center gap-1 border-b border-border-default px-2 pt-[env(safe-area-inset-top)] sm:px-4 lg:pt-0">
      <button
        type="button"
        onClick={onOpenList}
        aria-label={t('Чаты поддержки')}
        className="flex size-10 shrink-0 items-center justify-center rounded-full outline-none hover:bg-bg-subtle focus-visible:ring-2 focus-visible:ring-bg-inverse lg:hidden"
      >
        <Menu className="size-5" aria-hidden />
      </button>
      <div className="flex min-w-0 flex-1 flex-col px-2 py-2">
        <h1 className="truncate text-body-medium">{title}</h1>
        {subtitle && (
          <p className="flex items-center gap-1.5 truncate text-caption text-text-secondary">
            {subtitle}
          </p>
        )}
      </div>
      {actions}
      <Link
        to={base}
        aria-label={t('Новый чат')}
        className="flex size-10 shrink-0 items-center justify-center rounded-full outline-none hover:bg-bg-subtle focus-visible:ring-2 focus-visible:ring-bg-inverse lg:hidden"
      >
        <SquarePen className="size-5" aria-hidden />
      </Link>
    </header>
  )
}

function NewChat({
  base,
  rideId,
  driver,
  onOpenList,
}: {
  base: string
  rideId: string | null
  driver: boolean
  onOpenList: () => void
}) {
  const { user } = useSession()
  const assistant = useSupportAssistant()
  const ai = assistant.data?.available === true
  const action = useSupportAction()
  const client = useQueryClient()
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [sent, setSent] = useState<string | null>(null)
  const nonce = useRef({ body: '', id: crypto.randomUUID() })
  const send = (raw: string) => {
    const body = raw.trim()
    if (!body || action.isPending) return
    if (nonce.current.body !== body) nonce.current = { body, id: crypto.randomUUID() }
    setSent(body)
    setText('')
    action.mutate(
      {
        type: 'create',
        body: {
          client_request_id: nonce.current.id,
          category: rideId ? 'ride' : 'other',
          subject: subjectFrom(body),
          body,
          ride_id: rideId || undefined,
        },
      },
      {
        onSuccess: (data) => {
          if (!('owner_id' in data)) return
          const first: SupportMessage = {
            id: `local-${data.id}`,
            seq: 1,
            author_kind: 'human',
            author_id: user?.id ?? null,
            author_name: user?.username ?? '',
            author_role: user?.role ?? '',
            body,
            created_at: data.created_at,
          }
          client.setQueryData<Ticket>(['support', 'ticket', data.id], data)
          client.setQueryData<Conversation>(conversationKey(data.id), {
            items: [first],
            fetchedThrough: 1,
            hasOlder: false,
          })
          navigate(`${base}/${data.id}`, { replace: true })
        },
        onError: () => {
          setText(body)
          setSent(null)
        },
      },
    )
  }
  const prompts = driver ? DRIVER_PROMPTS : PASSENGER_PROMPTS
  return (
    <>
      <ChatHeader
        title={t('Новый чат')}
        subtitle={ai ? t('ИИ-помощник') : t('Поддержка TezJet')}
        base={base}
        onOpenList={onOpenList}
      />
      {sent === null ? (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto px-4 py-8">
          <div className="flex w-full max-w-xl flex-col items-center gap-5 text-center motion-safe:animate-fade-up">
            <span className="flex size-14 items-center justify-center rounded-full bg-brand-sky-soft text-brand-sky-ink">
              {ai ? <Bot className="size-7" aria-hidden /> : <Headset className="size-7" aria-hidden />}
            </span>
            <div className="flex flex-col gap-2">
              <h2 className="text-title">{t('Чем можем помочь?')}</h2>
              <OrnamentDivider className="mx-auto w-28" />
              <p className="text-callout text-text-secondary">
                {ai
                  ? t(
                      'ИИ-помощник сразу ответит на вопросы о поездках, оплате и документах. Если нужно, подключим оператора.',
                    )
                  : t('Опишите вопрос — оператор ответит в этом чате.')}
              </p>
            </div>
            {rideId && (
              <p className="rounded-full bg-bg-subtle px-4 py-2 text-caption text-text-secondary">
                {t('Чат будет связан с выбранной поездкой')}
              </p>
            )}
            <div className="grid w-full gap-2 sm:grid-cols-2">
              {prompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  disabled={action.isPending}
                  onClick={() => send(t(prompt))}
                  className="rounded-2xl border border-border-default px-4 py-3 text-left text-callout outline-none transition-colors hover:bg-bg-subtle focus-visible:ring-2 focus-visible:ring-bg-inverse disabled:opacity-50"
                >
                  {t(prompt)}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <ChatLog>
          <MessageRow
            message={{ author_kind: 'human', author_role: '', author_name: '', body: sent }}
            mine
            sending
          />
          {ai && <TypingIndicator queued />}
        </ChatLog>
      )}
      <Composer
        value={text}
        onChange={setText}
        onSend={() => send(text)}
        busy={action.isPending}
        placeholder={t('Напишите вопрос')}
        footer={ai ? t(AI_FOOTER) : undefined}
        error={action.error}
        autoFocus
      />
    </>
  )
}

function TicketChat({
  ticketId,
  base,
  onOpenList,
}: {
  ticketId: string
  base: string
  onOpenList: () => void
}) {
  const { user } = useSession()
  const ticket = useSupportTicket(ticketId)
  const action = useSupportAction()
  const handoff = useSupportAction()
  const client = useQueryClient()
  const [text, setText] = useState('')
  const [sending, setSending] = useState<string | null>(null)
  const nonce = useRef({ body: '', id: crypto.randomUUID() })
  const data = ticket.data
  const ai = data?.ai_available === true
  const callOperator = () => handoff.mutate({ type: 'handoff', id: ticketId })
  const send = () => {
    const body = text.trim()
    if (!body || action.isPending) return
    if (nonce.current.body !== body) nonce.current = { body, id: crypto.randomUUID() }
    setSending(body)
    setText('')
    action.mutate(
      { type: 'send', id: ticketId, body: { body, client_message_id: nonce.current.id } },
      {
        onSuccess: (message) => {
          if ('seq' in message)
            client.setQueryData<Conversation>(conversationKey(ticketId), (previous) => ({
              items: [...(previous?.items ?? []).filter((item) => item.seq !== message.seq), message],
              fetchedThrough: previous?.fetchedThrough ?? 0,
              hasOlder: previous?.hasOlder ?? false,
            }))
          client.setQueryData<Ticket>(['support', 'ticket', ticketId], (previous) =>
            previous?.ai_available && previous.ai_state !== 'running'
              ? { ...previous, ai_state: 'pending' }
              : previous,
          )
          nonce.current = { body: '', id: crypto.randomUUID() }
          setSending(null)
        },
        onError: () => {
          setText(body)
          setSending(null)
        },
      },
    )
  }
  const newChat = (
    <Link
      to={base}
      className="inline-flex min-h-10 items-center gap-2 rounded-full border border-border-default px-4 text-callout outline-none hover:bg-bg-subtle focus-visible:ring-2 focus-visible:ring-bg-inverse"
    >
      <Bot className="size-4" aria-hidden />
      {t('Новый чат с ИИ')}
    </Link>
  )
  return (
    <>
      <ChatHeader
        title={data?.subject ?? t('Чат поддержки')}
        subtitle={
          data &&
          (ai ? (
            <>
              <Bot className="size-3.5 shrink-0" aria-hidden />
              {t('Отвечает ИИ-помощник')}
            </>
          ) : data.status === 'resolved' ? (
            t('Вопрос решён')
          ) : (
            <>
              <Headset className="size-3.5 shrink-0" aria-hidden />
              {t('Отвечает оператор')}
            </>
          ))
        }
        actions={
          ai && (
            <Button
              size="md"
              variant="secondary"
              className="shrink-0 px-3"
              loading={handoff.isPending}
              onClick={callOperator}
            >
              <Headset />
              <span className="hidden sm:inline">{t('Позвать оператора')}</span>
              <span className="sm:hidden">{t('Оператор')}</span>
            </Button>
          )
        }
        base={base}
        onOpenList={onOpenList}
      />
      {handoff.error && (
        <div className="px-4 pt-3">
          <ErrorAlert error={handoff.error} />
        </div>
      )}
      {ticket.error && (
        <div className="mx-auto w-full max-w-3xl px-4 pt-6">
          <ErrorAlert error={ticket.error} />
        </div>
      )}
      {ticket.isPending && (
        <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-6">
          <Skeleton className="ml-auto h-12 w-2/3 rounded-3xl" />
          <Skeleton className="h-20 w-3/4 rounded-2xl" />
        </div>
      )}
      {data && (
        <>
          <TicketConversation
            ticket={data}
            viewerId={user?.id}
            admin={false}
            sending={sending}
            onCallOperator={callOperator}
            calling={handoff.isPending}
            newChat={newChat}
          />
          <Composer
            value={text}
            onChange={setText}
            onSend={send}
            busy={action.isPending}
            placeholder={ai ? t('Напишите вопрос') : t('Сообщение оператору')}
            footer={ai ? t(AI_FOOTER) : undefined}
            error={action.error}
            autoFocus
          />
        </>
      )}
    </>
  )
}

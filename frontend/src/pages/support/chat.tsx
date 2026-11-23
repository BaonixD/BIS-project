import { ArrowDown, ArrowUp, Bot, Headset } from 'lucide-react'
import {
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
  type Ref,
} from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { request, jsonBody } from '@/api/request'
import {
  assistantWorking,
  type MessagePage,
  type SupportMessage,
  type Ticket,
} from '@/hooks/use-support'
import { Button, Skeleton } from '@/components/ui-kit'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { t } from '@/i18n/core'
import {
  chatTime,
  conversationKey,
  hasVisibleText,
  mergeMessages,
  useChatScroll,
  type Conversation,
} from './chat-model'

export interface ChatLogHandle {
  atBottom: () => boolean
  keepPosition: (work: () => Promise<void>) => Promise<void>
}

export function ChatLog({
  children,
  handle,
  onBottomChange,
}: {
  children: ReactNode
  handle?: Ref<ChatLogHandle>
  onBottomChange?: (atBottom: boolean) => void
}) {
  const { scrollRef, contentRef, stick, atBottom, onScroll, scrollToBottom, keepPosition } =
    useChatScroll()
  useImperativeHandle(handle, () => ({ atBottom: () => stick.current, keepPosition }), [
    stick,
    keepPosition,
  ])
  useEffect(() => onBottomChange?.(atBottom), [atBottom, onBottomChange])
  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <div
        ref={scrollRef}
        onScroll={onScroll}
        role="log"
        aria-label={t('Переписка')}
        aria-live="polite"
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain"
      >
        <div
          ref={contentRef}
          className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6 sm:px-6"
        >
          {children}
        </div>
      </div>
      {!atBottom && (
        <button
          type="button"
          onClick={scrollToBottom}
          aria-label={t('Новые сообщения')}
          className="absolute bottom-3 left-1/2 flex size-9 -translate-x-1/2 items-center justify-center rounded-full border border-border-default bg-bg-canvas shadow-card outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
        >
          <ArrowDown className="size-4" aria-hidden />
        </button>
      )}
    </div>
  )
}

function Avatar({ kind, name }: { kind: 'assistant' | 'staff' | 'person'; name?: string }) {
  return (
    <span
      aria-hidden
      className={`flex size-8 shrink-0 items-center justify-center rounded-full text-caption ${kind === 'assistant' ? 'bg-brand-sky-soft text-brand-sky-ink' : 'border border-border-default bg-bg-canvas text-text-primary'}`}
    >
      {kind === 'assistant' ? (
        <Bot className="size-4" />
      ) : kind === 'staff' ? (
        <Headset className="size-4" />
      ) : (
        (name?.[0] ?? '?').toUpperCase()
      )}
    </span>
  )
}

export function MessageRow({
  message,
  mine,
  sending = false,
}: {
  message: Pick<SupportMessage, 'author_kind' | 'author_role' | 'author_name' | 'body'> & {
    created_at?: string
  }
  mine: boolean
  sending?: boolean
}) {
  const time = message.created_at ? chatTime(message.created_at) : null
  if (mine)
    return (
      <div className="flex justify-end motion-safe:animate-fade-up">
        <div className="flex max-w-[85%] flex-col items-end gap-1 sm:max-w-[75%]">
          <p
            className={`rounded-3xl bg-bg-muted px-4 py-2.5 text-callout whitespace-pre-wrap [overflow-wrap:anywhere] ${sending ? 'opacity-60' : ''}`}
          >
            {message.body}
          </p>
          <span className="px-2 text-caption text-text-tertiary">
            {sending ? t('Отправляем…') : time}
          </span>
        </div>
      </div>
    )
  const assistant = message.author_kind === 'assistant'
  const staff = message.author_role === 'admin'
  return (
    <div className="flex gap-3 motion-safe:animate-fade-up">
      <Avatar
        kind={assistant ? 'assistant' : staff ? 'staff' : 'person'}
        name={message.author_name}
      />
      <div className="flex min-w-0 flex-1 flex-col gap-1 pt-1">
        <p className="text-caption font-medium text-text-secondary">
          {assistant ? t('ИИ-помощник') : staff ? t('Оператор поддержки') : message.author_name}
        </p>
        <p className="text-callout leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere]">
          {message.body}
        </p>
        {time && <span className="text-caption text-text-tertiary">{time}</span>}
      </div>
    </div>
  )
}

export function TypingIndicator({ queued }: { queued: boolean }) {
  const label = queued ? t('Изучает вопрос…') : t('Пишет ответ…')
  return (
    <div className="flex gap-3 motion-safe:animate-fade-up" role="status" aria-label={label}>
      <Avatar kind="assistant" />
      <div className="flex min-w-0 flex-col gap-1.5 pt-1">
        <p className="text-caption font-medium text-text-secondary">{t('ИИ-помощник')}</p>
        <div className="flex items-center gap-3" aria-hidden>
          <span className="flex h-8 items-center gap-1 rounded-full bg-brand-sky-soft px-3">
            {[0, 1, 2].map((dot) => (
              <span
                key={dot}
                className="size-1.5 rounded-full bg-brand-sky-ink motion-safe:animate-typing-dot"
                style={{ animationDelay: `${dot * 0.15}s` }}
              />
            ))}
          </span>
          <span className="text-shimmer text-callout">{label}</span>
        </div>
      </div>
    </div>
  )
}

export function SystemNote({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div
      className="flex flex-col items-center gap-2 text-center motion-safe:animate-fade-up"
      role="status"
    >
      <p className="max-w-md rounded-2xl bg-bg-subtle px-4 py-2 text-caption text-text-secondary">
        {children}
      </p>
      {action}
    </div>
  )
}

function coarsePointer() {
  return typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches
}

export function Composer({
  value,
  onChange,
  onSend,
  busy = false,
  placeholder,
  footer,
  error,
  autoFocus = false,
}: {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  busy?: boolean
  placeholder: string
  footer?: ReactNode
  error?: Error | null
  autoFocus?: boolean
}) {
  const field = useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(() => {
    const element = field.current
    if (!element) return
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, 200)}px`
  }, [value])
  useEffect(() => {
    if (autoFocus && !coarsePointer()) field.current?.focus()
  }, [autoFocus])
  const ready = hasVisibleText(value) && !busy
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return
    if (coarsePointer()) return
    event.preventDefault()
    if (ready) onSend()
  }
  return (
    <div className="shrink-0 px-4 pt-2 pb-[calc(12px+env(safe-area-inset-bottom))] sm:px-6 lg:pb-5">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-2">
        <ErrorAlert error={error ?? null} />
        <form
          className="flex items-end gap-2 rounded-[28px] border border-border-default bg-bg-canvas py-2 pr-2 pl-5 shadow-card transition-colors focus-within:border-text-tertiary"
          onSubmit={(event) => {
            event.preventDefault()
            if (ready) onSend()
          }}
        >
          <label className="sr-only" htmlFor="support-message">
            {t('Сообщение')}
          </label>
          <textarea
            id="support-message"
            ref={field}
            rows={1}
            maxLength={2000}
            placeholder={placeholder}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={onKeyDown}
            className="max-h-[200px] min-h-10 flex-1 resize-none bg-transparent py-2 text-callout outline-none placeholder:text-text-tertiary"
          />
          {value.length > 1800 && (
            <span className="self-center text-caption text-text-tertiary">
              {value.length}/2000
            </span>
          )}
          <button
            type="submit"
            disabled={!ready}
            aria-label={t('Отправить')}
            className="flex size-10 shrink-0 items-center justify-center rounded-full bg-bg-inverse text-text-inverse transition-opacity outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse focus-visible:ring-offset-2 disabled:opacity-25"
          >
            <ArrowUp className="size-5" aria-hidden />
          </button>
        </form>
        {footer && <p className="text-center text-caption text-text-tertiary">{footer}</p>}
      </div>
    </div>
  )
}

/** Messages of one ticket: polling, older pages, read position and assistant notes. */
export function TicketConversation({
  ticket,
  viewerId,
  admin,
  sending,
  onCallOperator,
  calling,
  newChat,
}: {
  ticket: Ticket
  viewerId: string | undefined
  admin: boolean
  sending: string | null
  onCallOperator?: () => void
  calling?: boolean
  newChat?: ReactNode
}) {
  const client = useQueryClient()
  const key = conversationKey(ticket.id)
  const log = useRef<ChatLogHandle>(null)
  const [atBottom, setAtBottom] = useState(true)
  const readSeq = useRef(0)
  const pendingRead = useRef(false)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [olderError, setOlderError] = useState<Error | null>(null)
  const query = useQuery({
    queryKey: key,
    queryFn: async (): Promise<Conversation> => {
      const before = client.getQueryData<Conversation>(key)
      const page = await request<MessagePage>(
        `/support/tickets/${ticket.id}/messages${before ? `?after_seq=${before.fetchedThrough}` : ''}`,
      )
      const current = client.getQueryData<Conversation>(key)
      return {
        items: mergeMessages(current?.items ?? [], page.items),
        fetchedThrough: page.items.at(-1)?.seq ?? current?.fetchedThrough ?? 0,
        hasOlder: current?.hasOlder ?? page.has_more,
      }
    },
    refetchInterval: 5_000,
  })
  const items = query.data?.items ?? []
  const fetchedThrough = query.data?.fetchedThrough
  const refetch = query.refetch
  useEffect(() => {
    if (fetchedThrough !== undefined && ticket.last_message_seq > fetchedThrough) void refetch()
  }, [ticket.last_message_seq, fetchedThrough, refetch])

  const markRead = useCallback(() => {
    const seq = fetchedThrough ?? 0
    if (document.hidden || !(log.current?.atBottom() ?? true) || pendingRead.current) return
    if (seq <= readSeq.current) return
    pendingRead.current = true
    void request(`/support/tickets/${ticket.id}/read`, {
      method: 'POST',
      ...jsonBody({ last_read_seq: seq }),
    })
      .then(() => {
        readSeq.current = seq
        void client.invalidateQueries({ queryKey: ['support', 'unread'] })
        void client.invalidateQueries({ queryKey: ['support', 'tickets'] })
      })
      .catch(() => undefined)
      .finally(() => {
        pendingRead.current = false
      })
  }, [fetchedThrough, ticket.id, client])
  useEffect(() => {
    markRead()
    const onVisible = () => {
      if (!document.hidden) markRead()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [markRead, atBottom])

  const loadOlder = () => {
    const first = items[0]?.seq
    if (!first) return
    setLoadingOlder(true)
    setOlderError(null)
    const keep = log.current?.keepPosition ?? ((work: () => Promise<void>) => work())
    void keep(async () => {
        const page = await request<MessagePage>(
          `/support/tickets/${ticket.id}/messages?before_seq=${first}`,
        )
        client.setQueryData<Conversation>(key, (previous) => ({
          items: mergeMessages(previous?.items ?? [], page.items),
          fetchedThrough: previous?.fetchedThrough ?? 0,
          hasOlder: page.has_more,
        }))
    })
      .catch((error: Error) => setOlderError(error))
      .finally(() => setLoadingOlder(false))
  }

  const lastAssistant = items.findLastIndex((message) => message.author_kind === 'assistant')
  const staffAfterAssistant = items
    .slice(lastAssistant + 1)
    .some((message) => message.author_role === 'admin')
  const handedOver =
    ticket.support_mode === 'human' && lastAssistant >= 0 && !staffAfterAssistant
  const working = assistantWorking(ticket) || (sending !== null && ticket.ai_available)

  return (
    <ChatLog handle={log} onBottomChange={setAtBottom}>
      {query.data?.hasOlder && (
        <Button
          variant="ghost"
          size="md"
          className="self-center"
          loading={loadingOlder}
          onClick={loadOlder}
        >
          {t('Ранние сообщения')}
        </Button>
      )}
      <ErrorAlert error={query.error ?? olderError} />
      {query.isPending && (
        <div className="flex flex-col gap-4">
          <Skeleton className="ml-auto h-12 w-2/3 rounded-3xl" />
          <Skeleton className="h-20 w-3/4 rounded-2xl" />
        </div>
      )}
      {items.map((message) => (
        <MessageRow
          key={message.id}
          message={message}
          mine={message.author_id !== null && message.author_id === viewerId}
        />
      ))}
      {sending !== null && (
        <MessageRow
          message={{
            author_kind: 'human',
            author_role: '',
            author_name: '',
            body: sending,
          }}
          mine
          sending
        />
      )}
      {working && <TypingIndicator queued={ticket.ai_state !== 'running'} />}
      {!working && ticket.ai_available && ticket.ai_state === 'failed' && (
        <SystemNote
          action={
            onCallOperator && (
              <Button size="md" variant="secondary" loading={calling} onClick={onCallOperator}>
                <Headset />
                {t('Позвать оператора')}
              </Button>
            )
          }
        >
          {t('Помощник сейчас не смог ответить. Попробуйте ещё раз или позовите оператора.')}
        </SystemNote>
      )}
      {handedOver && (
        <SystemNote action={!admin && newChat}>
          {admin
            ? t('Пользователь позвал оператора. ИИ-помощник больше не отвечает в этом чате.')
            : t(
                'Чат передан оператору — ответ появится здесь. ИИ-помощник в этом чате больше не отвечает.',
              )}
        </SystemNote>
      )}
      {ticket.status === 'resolved' && (
        <SystemNote>
          {admin
            ? t('Вопрос решён')
            : t('Вопрос решён. Напишите, если нужна ещё помощь — чат откроется снова.')}
        </SystemNote>
      )}
    </ChatLog>
  )
}

import { useRef, useState } from 'react'
import { ArrowLeft, Bot, Headset } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { useSession } from '@/auth/use-session'
import { useHideBottomNav } from '@/components/layout/nav-visibility'
import { useSupportAction, useSupportTicket } from '@/hooks/use-support'
import { Button, Skeleton, StatusPill } from '@/components/ui-kit'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { t, useLocale } from '@/i18n/core'
import { supportCategory, supportStatus } from './support-labels'
import { Composer, TicketConversation } from './chat'
import { conversationKey, type Conversation } from './chat-model'

export function SupportThreadPage() {
  const { ticketId } = useParams()
  return <AdminThread key={ticketId} />
}

function AdminThread() {
  useLocale()
  useHideBottomNav(true)
  const { ticketId = '' } = useParams()
  const { user } = useSession()
  const ticket = useSupportTicket(ticketId)
  const action = useSupportAction()
  const status = useSupportAction()
  const handoff = useSupportAction()
  const client = useQueryClient()
  const [text, setText] = useState('')
  const [sending, setSending] = useState<string | null>(null)
  const nonce = useRef({ body: '', id: crypto.randomUUID() })
  const data = ticket.data
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
  return (
    <div className="flex h-dvh flex-col bg-bg-canvas lg:h-[calc(100dvh-var(--top-bar-height))]">
      <header className="shrink-0 border-b border-border-default px-4 pt-[calc(8px+env(safe-area-inset-top))] pb-3 sm:px-6 lg:pt-3">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-2">
          <Link
            to="/admin/support"
            className="-ml-2 inline-flex min-h-10 items-center gap-2 self-start rounded-md px-2 text-callout text-text-secondary outline-none hover:text-text-primary focus-visible:ring-2 focus-visible:ring-bg-inverse"
          >
            <ArrowLeft className="size-4" aria-hidden />
            {t('Все обращения')}
          </Link>
          <ErrorAlert error={ticket.error ?? status.error ?? handoff.error} />
          {ticket.isPending && <Skeleton className="h-12" />}
          {data && (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex min-w-0 flex-col gap-1">
                <div className="flex min-w-0 items-center gap-2">
                  <h1 className="truncate text-headline">{data.subject}</h1>
                  <StatusPill tone={data.status === 'resolved' ? 'success' : 'warning'}>
                    {supportStatus(data.status)}
                  </StatusPill>
                </div>
                <p className="flex flex-wrap items-center gap-x-2 text-caption text-text-secondary">
                  <span>@{data.owner_name}</span>
                  <span>· {supportCategory(data.category)}</span>
                  <span className="inline-flex items-center gap-1">
                    ·
                    {data.ai_available ? (
                      <>
                        <Bot className="size-3.5" aria-hidden /> {t('Отвечает ИИ-помощник')}
                      </>
                    ) : (
                      <>
                        <Headset className="size-3.5" aria-hidden /> {t('Отвечает оператор')}
                      </>
                    )}
                  </span>
                  {data.ride_id && (
                    <Link className="underline" to={`/admin/rides/${data.ride_id}`}>
                      {t('Связанная поездка')}
                    </Link>
                  )}
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                {data.ai_available && (
                  <Button
                    size="md"
                    variant="secondary"
                    loading={handoff.isPending}
                    onClick={() => handoff.mutate({ type: 'handoff', id: ticketId })}
                  >
                    <Headset />
                    {t('Подключиться')}
                  </Button>
                )}
                <Button
                  size="md"
                  variant="secondary"
                  loading={status.isPending}
                  onClick={() =>
                    status.mutate({
                      type: 'status',
                      id: ticketId,
                      status: data.status === 'resolved' ? 'in_progress' : 'resolved',
                    })
                  }
                >
                  {t(data.status === 'resolved' ? 'Открыть снова' : 'Решить вопрос')}
                </Button>
              </div>
            </div>
          )}
        </div>
      </header>
      {data && (
        <>
          <TicketConversation ticket={data} viewerId={user?.id} admin sending={sending} />
          <Composer
            value={text}
            onChange={setText}
            onSend={send}
            busy={action.isPending}
            placeholder={t('Ответ пользователю')}
            footer={
              data.ai_available
                ? t('Ваш ответ или смена статуса отключат помощника в этом обращении.')
                : undefined
            }
            error={action.error}
          />
        </>
      )}
    </div>
  )
}

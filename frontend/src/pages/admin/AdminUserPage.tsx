import { adminDate } from './admin-model'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { Dialog } from 'radix-ui'
import { ArrowLeft, ShieldAlert } from 'lucide-react'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Avatar } from '@/components/driver/Avatar'
import { Button, StatusPill, showToast } from '@/components/ui-kit'
import { useAccountAccess, useAdminUser } from '@/hooks/use-admin'
import { ROLE_PILL } from './admin-format'
import { AdminLayout, AdminLoading, FactList, RidesLink } from './admin-controls'

export function AdminUserPage() {
  const { userId } = useParams()
  const query = useAdminUser(userId)
  const access = useAccountAccess()
  const user = query.data
  const [confirm, setConfirm] = useState(false)
  const [reason, setReason] = useState('')
  const blocked = Boolean(user?.blocked_at)
  const close = () => {
    if (!access.isPending) {
      setConfirm(false)
      access.reset()
      setReason('')
    }
  }
  return (
    <AdminLayout
      title="Карточка пользователя"
      description="Доступ к сервису и история поездок."
      refreshing={query.isFetching}
      onRefresh={() => void query.refetch()}
    >
      <Link to="/admin/users" className="inline-flex items-center gap-2 text-callout">
        <ArrowLeft className="size-4" />
        Все пользователи
      </Link>
      <ErrorAlert error={query.error} />
      {query.isPending && <AdminLoading />}
      {user && (
        <div className="grid items-start gap-5 lg:grid-cols-2">
          <section className="rounded-lg bg-bg-canvas p-5">
            <div className="flex items-center gap-3">
              <Avatar name={user.display_name ?? user.username} size={64} />
              <div className="min-w-0">
                <h2 className="break-words text-headline">{user.display_name ?? user.username}</h2>
                <p className="text-caption text-text-secondary">@{user.username}</p>
                <StatusPill tone={ROLE_PILL[user.role].tone}>
                  {ROLE_PILL[user.role].label}
                </StatusPill>
              </div>
            </div>
            <FactList
              items={[
                ['Регистрация', adminDate(user.created_at)],
                [
                  'ID аккаунта',
                  <span className="select-all font-mono text-caption">{user.id}</span>,
                ],
              ]}
            />
            <div className="flex flex-wrap gap-4">
              {user.role !== 'admin' && <RidesLink userId={user.id} role={user.role} />}
              {user.role === 'driver' && (
                <Link
                  to={`/admin/drivers/${user.id}`}
                  className="text-callout underline underline-offset-4"
                >
                  Профиль водителя
                </Link>
              )}
            </div>
          </section>
          <section className="rounded-lg bg-bg-canvas p-5">
            <h2 className="text-headline">Доступ к сервису</h2>
            <div className="mt-4">
              <StatusPill tone={blocked ? 'danger' : 'success'}>
                {blocked ? 'Заблокирован' : 'Активен'}
              </StatusPill>
            </div>
            {blocked && (
              <FactList
                items={[
                  ['Дата блокировки', adminDate(user.blocked_at)],
                  ['Причина', user.block_reason],
                ]}
              />
            )}
            <p className="my-4 text-callout text-text-secondary">
              {user.role === 'admin'
                ? 'Аккаунты администраторов защищены от блокировки.'
                : blocked
                  ? 'Разблокировка разрешит новый вход. Водителю нужно будет снова выйти на линию.'
                  : 'Блокировка завершит все сессии пользователя. Водитель будет снят с линии. С активной поездкой или неполученными наличными блокировка недоступна.'}
            </p>
            {user.role !== 'admin' && (
              <Button
                variant={blocked ? 'primary' : 'danger'}
                size="md"
                onClick={() => setConfirm(true)}
              >
                {blocked ? 'Разблокировать аккаунт' : 'Заблокировать аккаунт'}
              </Button>
            )}
          </section>
        </div>
      )}
      <Dialog.Root
        open={confirm}
        onOpenChange={(open) => {
          if (!open) close()
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
          <Dialog.Content className="fixed top-1/2 left-1/2 z-50 flex max-h-[85dvh] w-[calc(100%-32px)] max-w-md -translate-x-1/2 -translate-y-1/2 flex-col gap-4 overflow-y-auto rounded-xl bg-bg-canvas p-6 shadow-sheet">
            <ShieldAlert className="size-7" />
            <Dialog.Title className="text-headline">
              {blocked ? 'Разблокировать аккаунт?' : 'Заблокировать аккаунт?'}
            </Dialog.Title>
            <Dialog.Description className="text-callout text-text-secondary">
              {blocked
                ? `Пользователь @${user?.username} снова сможет войти в сервис.`
                : `Пользователь @${user?.username} потеряет доступ, все его сессии завершатся.`}
            </Dialog.Description>
            <form
              className="flex flex-col gap-4"
              onSubmit={(event) => {
                event.preventDefault()
                if (!user) return
                access.mutate(
                  {
                    userId: user.id,
                    blocked: !blocked,
                    reason: !blocked ? reason.trim() : undefined,
                  },
                  {
                    onSuccess: () => {
                      setConfirm(false)
                      setReason('')
                      showToast({
                        title: blocked ? 'Аккаунт разблокирован' : 'Аккаунт заблокирован',
                      })
                    },
                  },
                )
              }}
            >
              {!blocked && (
                <label className="flex flex-col gap-2 text-callout">
                  Причина блокировки
                  <textarea
                    required
                    minLength={3}
                    maxLength={500}
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    className="min-h-24 rounded-md border border-border-default p-3 outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
                  />
                </label>
              )}
              <ErrorAlert error={access.error} />
              <Button
                type="submit"
                variant={blocked ? 'primary' : 'danger'}
                loading={access.isPending}
                disabled={!blocked && reason.trim().length < 3}
              >
                {blocked ? 'Разблокировать' : 'Подтвердить блокировку'}
              </Button>
              <Button variant="ghost" size="md" disabled={access.isPending} onClick={close}>
                Отмена
              </Button>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </AdminLayout>
  )
}

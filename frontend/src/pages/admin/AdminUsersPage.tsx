import { ADMIN_PAGE_SIZE, adminDate, useAdminFilters } from './admin-model'
import { Link } from 'react-router'
import { ChevronRight } from 'lucide-react'
import type { UserRole } from '@/api'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Avatar } from '@/components/driver/Avatar'
import { Button, Chip, StatusPill } from '@/components/ui-kit'
import { useAdminUsers } from '@/hooks/use-admin'
import { ROLE_PILL } from './admin-format'
import {
  AdminEmpty,
  AdminLayout,
  AdminLoading,
  AdminResults,
  AdminSearch,
  AdminSelect,
} from './admin-controls'

const ROLES = [
  ['all', 'Все'],
  ['passenger', 'Пассажиры'],
  ['driver', 'Водители'],
  ['admin', 'Администраторы'],
] as const

export function AdminUsersPage() {
  const { params, offset, update, reset } = useAdminFilters()
  const role = params.get('role') ?? 'all'
  const filter = ROLES.some(([id]) => id === role) ? role : 'all'
  const q = params.get('q') ?? ''
  const blocked = params.get('blocked')
  const users = useAdminUsers(filter === 'all' ? undefined : (filter as UserRole), {
    limit: ADMIN_PAGE_SIZE,
    offset,
    q: q || undefined,
    blocked: blocked === 'true' ? true : blocked === 'false' ? false : undefined,
  })
  return (
    <AdminLayout
      title="Пользователи"
      description="Найдите аккаунт, проверьте его поездки и управляйте доступом к сервису."
      refreshing={users.isFetching}
      onRefresh={() => void users.refetch()}
    >
      <div className="flex gap-2 overflow-x-auto">
        {ROLES.map(([id, text]) => (
          <Chip key={id} selected={filter === id} onClick={() => update({ role: id })}>
            {text}
          </Chip>
        ))}
      </div>
      <div className="grid items-end gap-3 rounded-lg bg-bg-canvas p-4 sm:grid-cols-[minmax(0,1fr)_180px_auto]">
        <AdminSearch
          key={q}
          value={q}
          placeholder="Поиск по имени, логину или телефону"
          onSearch={(value) => update({ q: value })}
        />
        <AdminSelect
          label="Доступ к сервису"
          value={blocked ?? ''}
          options={[
            ['', 'Все аккаунты'],
            ['false', 'Активные'],
            ['true', 'Заблокированные'],
          ]}
          onChange={(value) => update({ blocked: value })}
        />
        <Button variant="ghost" size="md" onClick={reset}>
          Сбросить
        </Button>
      </div>
      <ErrorAlert error={users.error} />
      {users.isPending && <AdminLoading />}
      {users.data?.items.length === 0 && <AdminEmpty onReset={reset} />}
      <ul
        className={`divide-y divide-border-default overflow-hidden rounded-lg bg-bg-canvas ${users.isPlaceholderData ? 'pointer-events-none opacity-50' : ''}`}
        aria-busy={users.isFetching}
      >
        {users.data?.items.map((user) => (
          <li key={user.id}>
            <Link
              to={`/admin/users/${user.id}`}
              className="flex items-center gap-3 p-4 outline-none hover:bg-bg-subtle focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-bg-inverse"
            >
              <Avatar name={user.display_name ?? user.username} size={40} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-body-medium text-text-primary">
                  {user.display_name ?? user.username}
                </p>
                <p className="truncate text-caption text-text-secondary">
                  @{user.username}
                  <span className="hidden sm:inline"> · с {adminDate(user.created_at)}</span>
                </p>
              </div>
              <div className="flex flex-col items-end gap-1 sm:flex-row">
                <StatusPill tone={ROLE_PILL[user.role].tone}>
                  {ROLE_PILL[user.role].label}
                </StatusPill>
                {user.blocked_at && <StatusPill tone="danger">Заблокирован</StatusPill>}
              </div>
              <ChevronRight className="size-4 text-text-tertiary" />
            </Link>
          </li>
        ))}
      </ul>
      <AdminResults
        total={users.data?.total}
        offset={offset}
        busy={users.isFetching}
        onPage={(value) => update({ offset: String(value) }, true)}
      />
    </AdminLayout>
  )
}

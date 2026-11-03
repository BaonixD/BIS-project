import { useState } from 'react'
import { Search } from 'lucide-react'
import type { AdminUser, UserRole } from '@/api'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Avatar } from '@/components/driver/Avatar'
import { Screen, ScreenColumn } from '@/components/driver/Screen'
import { Chip, Input, Skeleton, StatusPill } from '@/components/ui-kit'
import { useAdminUsers } from '@/hooks/use-admin'
import { ROLE_PILL } from './admin-format'

const FILTERS: { id: UserRole | 'all'; label: string }[] = [
  { id: 'all', label: 'Все' },
  { id: 'passenger', label: 'Пассажиры' },
  { id: 'driver', label: 'Водители' },
]

function UserRow({ user }: { user: AdminUser }) {
  const name = user.display_name ?? user.username
  const pill = ROLE_PILL[user.role]
  return (
    <li className="flex w-full items-center gap-3 overflow-hidden px-3 py-2.5">
      <Avatar name={name} size={40} />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <p className="truncate text-callout text-text-primary">{name}</p>
        <p className="truncate text-caption text-text-secondary">@{user.username}</p>
      </div>
      <StatusPill tone={pill.tone}>{pill.label}</StatusPill>
    </li>
  )
}

/** Figma 26:655: everyone with a role, search by name. */
export function AdminUsersPage() {
  const [filter, setFilter] = useState<UserRole | 'all'>('all')
  const [query, setQuery] = useState('')
  const users = useAdminUsers(filter === 'all' ? undefined : filter, { limit: 100 })
  const needle = query.trim().toLowerCase()
  const items = (users.data?.items ?? []).filter(
    (user) => !needle || `${user.display_name ?? ''} ${user.username}`.toLowerCase().includes(needle),
  )

  return (
    <Screen tone="subtle">
      <ScreenColumn className="gap-4 pt-[calc(64px+env(safe-area-inset-top))] pb-6 lg:max-w-2xl lg:pt-8">
        <h1 className="w-full text-display text-text-primary">Люди</h1>
        <Input
          icon={Search}
          placeholder="Поиск по имени"
          aria-label="Поиск по имени"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <div className="flex w-full items-center gap-2 overflow-x-auto scrollbar-none">
          {FILTERS.map((item) => (
            <Chip key={item.id} selected={item.id === filter} onClick={() => setFilter(item.id)}>
              {item.label}
            </Chip>
          ))}
        </div>
        <ErrorAlert error={users.error} />
        {users.isPending && <Skeleton className="h-75 w-full rounded-lg" />}
        {users.data && items.length === 0 && (
          <p className="w-full rounded-lg bg-bg-canvas p-5 text-center text-callout text-text-secondary">Никого не нашли</p>
        )}
        {items.length > 0 && (
          <ul className="flex w-full flex-col overflow-hidden rounded-lg bg-bg-canvas p-2">
            {items.map((user) => (
              <UserRow key={user.id} user={user} />
            ))}
          </ul>
        )}
      </ScreenColumn>
    </Screen>
  )
}

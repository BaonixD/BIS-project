import { useState } from 'react'
import type { UserRole } from '@/api'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { PageHeader } from '@/components/common/PageHeader'
import { Pagination } from '@/components/common/Pagination'
import { PageContainer } from '@/components/layout/PageContainer'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { useAdminUsers } from '@/hooks/use-admin'
import { formatDateTime } from '@/lib/format'
import { ROLE_LABELS } from '@/lib/labels'

const PAGE_SIZE = 20
const ALL_ROLES = 'all'

export function AdminUsersPage() {
  const [role, setRole] = useState<UserRole | typeof ALL_ROLES>(ALL_ROLES)
  const [offset, setOffset] = useState(0)
  const users = useAdminUsers(role === ALL_ROLES ? undefined : role, { limit: PAGE_SIZE, offset })

  return (
    <PageContainer>
      <PageHeader title="Пользователи" />
      <div className="pb-4">
        <Select
          value={role}
          onValueChange={(value) => {
            setRole(value as UserRole | typeof ALL_ROLES)
            setOffset(0)
          }}
        >
          <SelectTrigger className="w-full sm:w-56" aria-label="Роль">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_ROLES}>Все роли</SelectItem>
            {(Object.keys(ROLE_LABELS) as UserRole[]).map((value) => (
              <SelectItem key={value} value={value}>{ROLE_LABELS[value]}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {users.isPending && <Skeleton className="h-40" />}
      {users.isError && <ErrorAlert error={users.error} />}
      {users.data && users.data.items.length === 0 && <EmptyState>Нет пользователей</EmptyState>}
      {users.data && (
        <>
          <ul className="grid gap-2">
            {users.data.items.map((user) => (
              <li key={user.id}>
                <Card className="py-3">
                  <CardContent className="flex items-center justify-between gap-2 px-4">
                    <div>
                      <p className="font-medium">{user.display_name ?? user.username}</p>
                      <p className="text-xs text-muted-foreground">@{user.username} · {formatDateTime(user.created_at)}</p>
                    </div>
                    <Badge variant="outline">{ROLE_LABELS[user.role]}</Badge>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
          <Pagination offset={offset} limit={PAGE_SIZE} total={users.data.total} onChange={setOffset} />
        </>
      )}
    </PageContainer>
  )
}

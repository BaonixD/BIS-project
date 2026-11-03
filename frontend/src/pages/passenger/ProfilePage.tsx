import { KeyRound, LogOut, Phone, Settings, User } from 'lucide-react'
import { useSession } from '@/auth/use-session'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { RoundButton } from '@/components/passenger/layout'
import { ListRow, Skeleton } from '@/components/ui-kit'
import { useMyProfile } from '@/hooks/use-profile'
import { ROLE_LABELS } from '@/lib/labels'
import { initials } from './model/format'

/** Figma Profile 5:623. */
export function ProfilePage() {
  const profile = useMyProfile()
  const { logout } = useSession()
  const data = profile.data
  const name = data?.display_name || data?.username || ''

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 pt-[17px] pb-6 lg:pt-8">
      <div className="flex w-full items-center gap-4">
        <span className="flex size-18 shrink-0 items-center justify-center rounded-full bg-bg-muted text-headline text-text-primary">
          {data ? initials(name) : ''}
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          {data ? (
            <>
              <h1 className="truncate text-title text-text-primary">{name.split(/\s+/)[0]}</h1>
              <p className="truncate text-callout text-text-secondary">
                @{data.username} · {ROLE_LABELS[data.role].toLowerCase()}
              </p>
            </>
          ) : (
            <Skeleton className="h-12 w-40" />
          )}
        </div>
        <RoundButton to="/profile/settings" icon={Settings} label="Настройки" />
      </div>
      <ErrorAlert error={profile.error} />
      {data && (
        <div className="flex w-full flex-col">
          <ListRow icon={User} title="Имя" subtitle={data.display_name || 'Не указано'} />
          <ListRow icon={Phone} title="Телефон" subtitle={data.phone || 'Не указан'} />
          <ListRow icon={KeyRound} title="Вход" subtitle={`Логин и пароль · @${data.username}`} />
        </div>
      )}
      <button
        type="button"
        disabled={logout.isPending}
        onClick={() => logout.mutate()}
        className="flex w-full items-center gap-3 rounded-md py-3 text-left text-body-medium text-accent-danger outline-none transition-opacity active:opacity-60 focus-visible:ring-2 focus-visible:ring-bg-inverse disabled:opacity-40"
      >
        <LogOut className="size-6 shrink-0" strokeWidth={2} aria-hidden />
        Выйти из аккаунта
      </button>
    </div>
  )
}

import { KeyRound, LogOut, Phone, Settings, Star } from 'lucide-react'
import googleIcon from '@/assets/icons/google.svg'
import { formatRating } from '@/api/driver-types'
import { useSession } from '@/auth/use-session'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { GroupedRow, GroupedSection, ProfileHeaderCard } from '@/components/common/GroupedList'
import { Skeleton } from '@/components/ui-kit'
import { useMyProfile } from '@/hooks/use-profile'
import { ROLE_LABELS } from '@/lib/labels'
import { initials } from './model/format'

/** Figma Profile 5:623: grouped cards on the subtle background. */
export function ProfilePage() {
  const profile = useMyProfile()
  const { logout } = useSession()
  const data = profile.data
  const name = data?.display_name || data?.username || ''
  const google = data?.login_method === 'google'

  return (
    <div className="min-h-dvh bg-bg-subtle">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 pt-[64px] pb-6 lg:pt-8">
        <h1 className="px-1 text-display text-text-primary">Профиль</h1>
        <ErrorAlert error={profile.error} />
        {data ? (
          <ProfileHeaderCard
            to="/profile/settings"
            avatar={
              <span className="flex size-16 shrink-0 items-center justify-center rounded-full bg-bg-muted text-headline text-text-primary">
                {initials(name)}
              </span>
            }
            name={name}
            subtitle={`@${data.username} · ${ROLE_LABELS[data.role].toLowerCase()}`}
          />
        ) : (
          <Skeleton className="h-24 w-full rounded-lg" />
        )}
        {data && (
          <GroupedSection title="Аккаунт">
            <GroupedRow icon={Phone} tone="bg-accent-success" title="Телефон" value={data.phone || 'Не указан'} />
            <GroupedRow
              icon={KeyRound}
              iconNode={google ? <img src={googleIcon} alt="" className="size-[18px]" /> : undefined}
              tone={google ? 'bg-bg-canvas ring-1 ring-border-default' : 'bg-text-tertiary'}
              title="Вход"
              value={google ? (data.email ?? 'Google') : 'Логин и пароль'}
            />
            <GroupedRow icon={Star} tone="bg-accent-warning" title="Рейтинг" value={formatRating(data.rating) ?? 'Пока нет оценок'} />
          </GroupedSection>
        )}
        <GroupedSection>
          <GroupedRow icon={Settings} tone="bg-text-tertiary" title="Настройки" to="/profile/settings" />
        </GroupedSection>
        <GroupedSection>
          <GroupedRow
            icon={LogOut}
            tone="bg-accent-danger"
            title="Выйти из аккаунта"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
            chevron={false}
          />
        </GroupedSection>
      </div>
    </div>
  )
}

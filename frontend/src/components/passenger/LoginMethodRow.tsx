import { t, useLocale } from '@/i18n/core'
import { KeyRound } from 'lucide-react'
import type { MyProfile } from '@/api'
import googleIcon from '@/assets/icons/google.svg'
import { ListRow } from '@/components/ui-kit'
/** Figma 5:623 / 12:604 «Вход»: Google with its email, or username and password. */
export function LoginMethodRow({
  profile,
  showUsername = false,
}: {
  profile: MyProfile
  showUsername?: boolean
}) {
  useLocale()
  if (profile.login_method === 'google') {
    return (
      <ListRow
        leading={
          <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-bg-muted">
            <img src={googleIcon} alt="" className="size-6" />
          </span>
        }
        title={t('Вход')}
        subtitle={profile.email ? `Google · ${profile.email}` : 'Google'}
      />
    )
  }
  const subtitle = showUsername
    ? t('Логин и пароль · @{p0}', { p0: profile.username })
    : t('Логин и пароль')
  return <ListRow icon={KeyRound} title={t('Вход')} subtitle={subtitle} />
}

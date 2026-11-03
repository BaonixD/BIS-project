import { KeyRound } from 'lucide-react'
import type { MyProfile } from '@/api'
import googleIcon from '@/assets/icons/google.svg'
import { ListRow } from '@/components/ui-kit'

/** Figma 5:623 / 12:604 «Вход»: Google with its email, or username and password. */
export function LoginMethodRow({ profile, showUsername = false }: { profile: MyProfile; showUsername?: boolean }) {
  if (profile.login_method === 'google') {
    return (
      <ListRow
        leading={
          <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-bg-muted">
            <img src={googleIcon} alt="" className="size-6" />
          </span>
        }
        title="Вход"
        subtitle={profile.email ? `Google · ${profile.email}` : 'Google'}
      />
    )
  }
  const subtitle = showUsername ? `Логин и пароль · @${profile.username}` : 'Логин и пароль'
  return <ListRow icon={KeyRound} title="Вход" subtitle={subtitle} />
}

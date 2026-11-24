import { t, useLocale } from '@/i18n/core'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { AtSign, Phone, User } from 'lucide-react'
import type { MyProfile } from '@/api'
import { LoginMethodRow } from '@/components/passenger/LoginMethodRow'
import { FullScreen, ScreenHeader, SectionLabel } from '@/components/passenger/layout'
import { Button, Input, ListRow, Skeleton, showToast } from '@/components/ui-kit'
import { useMyProfile, useUpdateMyProfile } from '@/hooks/use-profile'
import { passengerErrorMessage } from './model/errors'
function SettingsForm({ profile }: { profile: MyProfile }) {
  useLocale()
  const navigate = useNavigate()
  const update = useUpdateMyProfile()
  const [displayName, setDisplayName] = useState(profile.display_name ?? '')
  const [phone, setPhone] = useState(profile.phone ?? '')
  const submit = (event: FormEvent) => {
    event.preventDefault()
    update.mutate(
      {
        ...(displayName.trim() && { display_name: displayName.trim() }),
        ...(phone.trim() && { phone: phone.trim() }),
      },
      {
        onSuccess: () => {
          showToast({ title: t('Сохранено') })
          navigate('/profile')
        },
      },
    )
  }
  return (
    <form
      onSubmit={submit}
      className="mx-auto flex min-h-full w-full max-w-[420px] flex-col px-4 pt-[calc(56px+env(safe-area-inset-top))] pb-[34px] lg:pt-8"
    >
      <div className="flex w-full flex-col gap-5">
        <ScreenHeader title={t('Настройки')} back={{ to: '/profile' }} />
        <SectionLabel>{t('ПРОФИЛЬ')}</SectionLabel>
        <div className="flex w-full flex-col gap-3">
          <Input
            icon={User}
            aria-label={t('Имя')}
            placeholder={t('Имя')}
            autoComplete="name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
          <Input
            icon={Phone}
            aria-label={t('Телефон')}
            type="tel"
            placeholder="+7 7XX XXX XX XX"
            autoComplete="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </div>
        <SectionLabel>{t('АККАУНТ')}</SectionLabel>
        <div className="flex w-full flex-col">
          <ListRow icon={AtSign} title={t('Имя пользователя')} subtitle={`@${profile.username}`} />
          <LoginMethodRow profile={profile} />
        </div>
      </div>
      <div className="mt-auto flex w-full flex-col gap-3 pt-6">
        {update.error && (
          <p role="alert" className="text-caption text-accent-danger">
            {passengerErrorMessage(update.error)}
          </p>
        )}
        <Button type="submit" className="w-full" loading={update.isPending}>
          {t('Сохранить')}
        </Button>
      </div>
    </form>
  )
}
/** Figma Settings 12:604. */
export function SettingsPage() {
  useLocale()
  const profile = useMyProfile()
  return (
    <FullScreen>
      {profile.data ? (
        <SettingsForm profile={profile.data} />
      ) : (
        <div className="mx-auto flex w-full max-w-[420px] flex-col gap-5 px-4 pt-[calc(56px+env(safe-area-inset-top))]">
          <ScreenHeader title={t('Настройки')} back={{ to: '/profile' }} />
          <Skeleton className="h-32 w-full rounded-lg" />
        </div>
      )}
    </FullScreen>
  )
}

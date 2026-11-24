import { SupportLink } from '@/components/common/SupportLink'
import { MapThemeSwitch } from '@/components/common/MapThemeSwitch'
import { TitleOrnament } from '@/components/common/Ornament'
import { Achievements } from '@/components/common/Achievements'
import { LanguageSwitcher } from '@/i18n/LanguageSwitcher'
import { t, useLocale } from '@/i18n/core'
import {
  Car,
  CreditCard,
  Hash,
  LogOut,
  Phone,
  Settings,
  ShieldCheck,
  Star,
  Timer,
} from 'lucide-react'
import { formatRating, TARIFF_LABELS, vehicleCategories } from '@/api/driver-types'
import { useSession } from '@/auth/use-session'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { GroupedRow, GroupedSection, ProfileHeaderCard } from '@/components/common/GroupedList'
import { Avatar } from '@/components/driver/Avatar'
import { Skeleton, StatusPill } from '@/components/ui-kit'
import { useDriverProfile } from '@/hooks/use-driver'
import { APPROVAL_STATUS_LABELS } from '@/lib/labels'
/** Figma 6:348: grouped cards — approval, vehicle, contacts, settings and logout. */
export function DriverProfilePage() {
  useLocale()
  const { user, logout } = useSession()
  const driver = useDriverProfile()
  const data = driver.data
  const name = data?.full_name ?? user?.username ?? ''
  const approved = data?.approval_status === 'approved'
  const vehicle = data?.vehicle
  return (
    <div className="min-h-dvh bg-bg-subtle">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 pt-[calc(64px+env(safe-area-inset-top))] pb-6 lg:pt-8">
        <div className="flex flex-col gap-2 px-1">
          <h1 className="text-display text-text-primary">{t('Профиль')}</h1>
          <TitleOrnament />
        </div>
        <div className="flex justify-end lg:hidden">
          <LanguageSwitcher />
        </div>
        <ErrorAlert error={driver.error} />
        {data ? (
          <ProfileHeaderCard
            to="/driver/settings"
            avatar={
              <Avatar
                name={name}
                size={64}
                className="bg-brand-sky-soft text-brand-sky-ink ring-2 ring-brand-gold ring-offset-2 ring-offset-bg-canvas"
              />
            }
            name={name}
            subtitle={t('@{p0} · водитель', { p0: user?.username ?? '' })}
          />
        ) : (
          <Skeleton className="h-24 w-full rounded-lg" />
        )}
        {data && (
          <>
            <GroupedSection title={t('Работа')}>
              <GroupedRow
                icon={approved ? ShieldCheck : Timer}
                tone={approved ? 'bg-accent-success' : 'bg-accent-warning'}
                title={t('Допуск')}
                value={
                  <StatusPill tone={approved ? 'success' : 'warning'}>
                    {APPROVAL_STATUS_LABELS()[data.approval_status]}
                  </StatusPill>
                }
              />
              <GroupedRow
                icon={Star}
                tone="bg-accent-warning"
                title={t('Рейтинг')}
                value={formatRating(data.rating) ?? t('Пока нет оценок')}
              />
            </GroupedSection>
            <GroupedSection title={t('Автомобиль')}>
              <GroupedRow
                icon={Car}
                tone="bg-accent-info"
                title={t('Машина')}
                value={
                  vehicle
                    ? `${vehicle.make} ${vehicle.model} · ${vehicle.color}`
                    : t('Не добавлена')
                }
              />
              {vehicle && (
                <GroupedRow
                  icon={Hash}
                  tone="bg-text-tertiary"
                  title={t('Госномер')}
                  value={vehicle.plate_number}
                />
              )}
              {vehicle && (
                <div className="border-t border-border-default px-4 py-3">
                  <p className="mb-2 text-callout text-text-primary">{t('Доступные тарифы')}</p>
                  <div className="flex flex-wrap gap-2">
                    {vehicleCategories(vehicle).map((category) => (
                      <StatusPill key={category}>{TARIFF_LABELS()[category]}</StatusPill>
                    ))}
                  </div>
                </div>
              )}
            </GroupedSection>
            <GroupedSection title={t('Контакты')}>
              <GroupedRow
                icon={Phone}
                tone="bg-accent-success"
                title={t('Телефон')}
                value={data.phone ?? t('Не указан')}
              />
              <GroupedRow
                icon={CreditCard}
                tone="bg-text-tertiary"
                title={t('Удостоверение')}
                value={data.license_number ?? t('Не указано')}
              />
            </GroupedSection>
          </>
        )}
        <SupportLink />
        <Achievements />
        <MapThemeSwitch />
        <GroupedSection>
          <GroupedRow icon={CreditCard} tone="bg-accent-info" title={t("Документы")} to="/driver/documents" />
          <GroupedRow
            icon={Settings}
            tone="bg-text-tertiary"
            title={t('Настройки')}
            to="/driver/settings"
          />
        </GroupedSection>
        <GroupedSection>
          <GroupedRow
            icon={LogOut}
            tone="bg-accent-danger"
            title={t('Выйти из аккаунта')}
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
            chevron={false}
          />
        </GroupedSection>
      </div>
    </div>
  )
}

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
  const { user, logout } = useSession()
  const driver = useDriverProfile()
  const data = driver.data
  const name = data?.full_name ?? user?.username ?? ''
  const approved = data?.approval_status === 'approved'
  const vehicle = data?.vehicle

  return (
    <div className="min-h-dvh bg-bg-subtle">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 pt-[calc(64px+env(safe-area-inset-top))] pb-6 lg:pt-8">
        <h1 className="px-1 text-display text-text-primary">Профиль</h1>
        <ErrorAlert error={driver.error} />
        {data ? (
          <ProfileHeaderCard
            to="/driver/settings"
            avatar={<Avatar name={name} size={64} />}
            name={name}
            subtitle={`@${user?.username ?? ''} · водитель`}
          />
        ) : (
          <Skeleton className="h-24 w-full rounded-lg" />
        )}
        {data && (
          <>
            <GroupedSection title="Работа">
              <GroupedRow
                icon={approved ? ShieldCheck : Timer}
                tone={approved ? 'bg-accent-success' : 'bg-accent-warning'}
                title="Допуск"
                value={
                  <StatusPill tone={approved ? 'success' : 'warning'}>
                    {APPROVAL_STATUS_LABELS[data.approval_status]}
                  </StatusPill>
                }
              />
              <GroupedRow
                icon={Star}
                tone="bg-accent-warning"
                title="Рейтинг"
                value={formatRating(data.rating) ?? 'Пока нет оценок'}
              />
            </GroupedSection>
            <GroupedSection title="Автомобиль">
              <GroupedRow
                icon={Car}
                tone="bg-accent-info"
                title="Машина"
                value={
                  vehicle ? `${vehicle.make} ${vehicle.model} · ${vehicle.color}` : 'Не добавлена'
                }
              />
              {vehicle && (
                <GroupedRow
                  icon={Hash}
                  tone="bg-text-tertiary"
                  title="Госномер"
                  value={vehicle.plate_number}
                />
              )}
              {vehicle && (
                <div className="border-t border-border-default px-4 py-3">
                  <p className="mb-2 text-callout text-text-primary">Доступные тарифы</p>
                  <div className="flex flex-wrap gap-2">
                    {vehicleCategories(vehicle).map((category) => (
                      <StatusPill key={category}>{TARIFF_LABELS[category]}</StatusPill>
                    ))}
                  </div>
                </div>
              )}
            </GroupedSection>
            <GroupedSection title="Контакты">
              <GroupedRow
                icon={Phone}
                tone="bg-accent-success"
                title="Телефон"
                value={data.phone ?? 'Не указан'}
              />
              <GroupedRow
                icon={CreditCard}
                tone="bg-text-tertiary"
                title="Удостоверение"
                value={data.license_number ?? 'Не указано'}
              />
            </GroupedSection>
          </>
        )}
        <GroupedSection>
          <GroupedRow
            icon={Settings}
            tone="bg-text-tertiary"
            title="Настройки"
            to="/driver/settings"
          />
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

import { Link } from 'react-router'
import { Car, CreditCard, LogOut, Phone, Settings, ShieldCheck, Timer } from 'lucide-react'
import { formatRating, TARIFF_LABELS, type NextDriver } from '@/api/next-contract-driver'
import { useSession } from '@/auth/use-session'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Avatar } from '@/components/driver/Avatar'
import { Screen, ScreenColumn } from '@/components/driver/Screen'
import { ListRow, Skeleton, StatusPill } from '@/components/ui-kit'
import { useDriverProfile } from '@/hooks/use-driver'

function InfoCard({ icon: Icon, title, text, trailing }: { icon: typeof Car; title: string; text: string; trailing?: React.ReactNode }) {
  return (
    <div className="flex w-full items-center gap-3 overflow-hidden rounded-lg bg-bg-subtle p-4">
      <Icon className="size-6 shrink-0 text-text-primary" strokeWidth={2} aria-hidden />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <p className="text-body-medium text-text-primary">{title}</p>
        <p className="text-caption text-text-secondary">{text}</p>
      </div>
      {trailing}
    </div>
  )
}

function ApprovalCard({ driver }: { driver: NextDriver }) {
  if (driver.approval_status === 'approved') {
    return (
      <InfoCard
        icon={ShieldCheck}
        title="Допуск получен"
        text="Можно выходить на линию и принимать заказы."
        trailing={<StatusPill tone="success">approved</StatusPill>}
      />
    )
  }
  return (
    <InfoCard
      icon={Timer}
      title="Ждёт проверки"
      text="Администратор проверит данные. После одобрения можно выйти на линию."
      trailing={<StatusPill tone="warning">pending</StatusPill>}
    />
  )
}

function VehicleCard({ driver }: { driver: NextDriver }) {
  const vehicle = driver.vehicle
  if (!vehicle) return <InfoCard icon={Car} title="Машина не добавлена" text="Добавьте её в настройках" />
  const carClass =
    driver.approval_status === 'approved' && vehicle.car_class ? ` · ${TARIFF_LABELS[vehicle.car_class]}` : ''
  return (
    <InfoCard
      icon={Car}
      title={`${vehicle.make} ${vehicle.model} · ${vehicle.color}`}
      text={`Госномер ${vehicle.plate_number}${carClass}`}
    />
  )
}

function ratingSuffix(driver: NextDriver): string {
  const rating = formatRating(driver.rating)
  return rating ? ` · ${rating}` : ''
}

/** Figma 6:348: profile, approval, vehicle and contacts. */
export function DriverProfilePage() {
  const { user, logout } = useSession()
  const driver = useDriverProfile()
  const data = driver.data
  const name = data?.full_name ?? user?.username ?? ''

  return (
    <Screen>
      <ScreenColumn className="gap-5 pt-[calc(17px+env(safe-area-inset-top))] pb-6">
        <div className="flex w-full items-center gap-4">
          <Avatar name={name} size={64} />
          <div className="flex min-w-0 flex-1 flex-col gap-0.5">
            <h1 className="truncate text-headline text-text-primary">{name}</h1>
            <p className="truncate text-callout text-text-secondary">
              @{user?.username} · водитель{data ? ratingSuffix(data) : ''}
            </p>
          </div>
          <Link
            to="/driver/settings"
            aria-label="Настройки"
            className="flex size-11 shrink-0 items-center justify-center rounded-full bg-bg-subtle text-text-primary outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
          >
            <Settings className="size-6" strokeWidth={2} aria-hidden />
          </Link>
        </div>
        {driver.isPending && <Skeleton className="h-60 w-full rounded-lg" />}
        <ErrorAlert error={driver.error} />
        {data && (
          <>
            <ApprovalCard driver={data} />
            <VehicleCard driver={data} />
            <div className="flex w-full flex-col">
              <ListRow icon={Phone} title="Телефон" subtitle={data.phone ?? 'Не указан'} />
              <ListRow
                icon={CreditCard}
                title="Водительское удостоверение"
                subtitle={data.license_number ?? 'Не указано'}
              />
            </div>
          </>
        )}
        <button
          type="button"
          disabled={logout.isPending}
          onClick={() => logout.mutate()}
          className="flex w-full items-center gap-3 py-3 text-accent-danger outline-none focus-visible:underline disabled:opacity-40"
        >
          <LogOut className="size-6 shrink-0" strokeWidth={2} aria-hidden />
          <span className="text-body-medium">Выйти из аккаунта</span>
        </button>
      </ScreenColumn>
    </Screen>
  )
}

import { APPROVAL_STATUS_LABELS } from '@/lib/labels'
import { Link, useParams } from 'react-router'
import { Check, CircleAlert } from 'lucide-react'
import { vehicleCategoryLabel, type NextAdminDriver } from '@/api/driver-types'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { FullScreenLoader } from '@/components/common/FullScreenLoader'
import { Avatar } from '@/components/driver/Avatar'
import { BackHeader } from '@/components/driver/BackHeader'
import { Screen, ScreenColumn, ScreenFooter } from '@/components/driver/Screen'
import { Button, StatusPill } from '@/components/ui-kit'
import { useAdminDriver } from '@/hooks/use-admin'
import { RidesLink } from './admin-controls'
import { DRIVER_FIELD_LABELS } from '@/lib/labels'
import { CarClassSheet } from './CarClassSheet'
import { useApproveFlow } from './use-approve-flow'

const registeredFormat = new Intl.DateTimeFormat('ru-RU', {
  timeZone: 'Asia/Almaty',
  day: 'numeric',
  month: 'long',
})

function Facts({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="flex w-full flex-col gap-2.5 overflow-hidden rounded-lg bg-bg-subtle p-4 text-callout">
      {rows.map(([label, value]) => (
        <div key={label} className="flex w-full items-start gap-3">
          <dt className="min-w-0 flex-1 text-text-secondary">{label}</dt>
          <dd className="max-w-[60%] break-words text-right text-text-primary">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function DriverDetails({ driver }: { driver: NextAdminDriver }) {
  const name = driver.full_name ?? driver.username
  const vehicle = driver.vehicle
  const vehicleRows: [string, string][] = [
    ['Машина', vehicle ? `${vehicle.make} ${vehicle.model}` : '—'],
    ['Цвет', vehicle?.color ?? '—'],
    ['Госномер', vehicle?.plate_number ?? '—'],
  ]
  if (driver.approval_status === 'approved' && vehicle?.car_class) {
    vehicleRows.push(['Категории', vehicleCategoryLabel(vehicle)])
  }
  const missing = driver.missing_fields.map((field) => DRIVER_FIELD_LABELS[field] ?? field)
  return (
    <>
      <div className="flex w-full items-center gap-4">
        <Avatar name={name} size={64} />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <p className="truncate text-headline text-text-primary">{name}</p>
          <p className="truncate text-caption text-text-secondary">
            @{driver.username} · зарегистрирован{' '}
            {registeredFormat.format(new Date(driver.created_at))}
          </p>
        </div>
      </div>
      <Facts
        rows={[
          ['Телефон', driver.phone ?? '—'],
          ['Права', driver.license_number ?? '—'],
        ]}
      />
      <Facts rows={vehicleRows} />
      <div className="flex w-full items-center gap-2.5">
        {missing.length === 0 ? (
          <Check className="size-6 shrink-0 text-accent-success" strokeWidth={2} aria-hidden />
        ) : (
          <CircleAlert className="size-6 shrink-0 text-accent-danger" strokeWidth={2} aria-hidden />
        )}
        <p className="text-callout text-text-secondary">
          {missing.length === 0
            ? 'Все обязательные поля заполнены'
            : `Не заполнено: ${missing.join(', ')}`}
        </p>
      </div>
    </>
  )
}

/** Figma 26:764: a driver's application. */
export function AdminDriverPage() {
  const { driverId } = useParams()
  const drivers = useAdminDriver(driverId)
  const flow = useApproveFlow()
  if (drivers.isPending) return <FullScreenLoader />
  const driver = drivers.data ?? null
  const approved = driver?.approval_status === 'approved'

  return (
    <Screen overNav>
      <ScreenColumn className="gap-4 pt-[calc(56px+env(safe-area-inset-top))] pb-32">
        <BackHeader
          title="Заявка водителя"
          fallback="/admin"
          trailing={
            driver && (
              <StatusPill tone={approved ? 'success' : 'warning'}>
                {APPROVAL_STATUS_LABELS[driver.approval_status]}
              </StatusPill>
            )
          }
        />
        <ErrorAlert error={drivers.error} />
        {driver ? (
          <>
            <DriverDetails driver={driver} />
            {driver.blocked_at && <StatusPill tone="danger">Аккаунт заблокирован</StatusPill>}
            <RidesLink userId={driver.id} role="driver">
              Поездки водителя
            </RidesLink>
            <Link
              to={`/admin/users/${driver.id}`}
              className="text-callout underline underline-offset-4"
            >
              Управление доступом к аккаунту
            </Link>
          </>
        ) : (
          !drivers.error && <p className="text-callout text-text-secondary">Водитель не найден</p>
        )}
      </ScreenColumn>
      {driver && (
        <ScreenFooter>
          <Button
            className="w-full"
            disabled={Boolean(driver.blocked_at)}
            onClick={() => flow.open(driver)}
          >
            {approved ? 'Сменить класс машины' : 'Одобрить водителя'}
          </Button>
        </ScreenFooter>
      )}
      {flow.target && (
        <CarClassSheet
          initial={flow.target.vehicle?.car_class ?? 'economy'}
          confirmLabel={approved ? 'Сохранить класс' : 'Одобрить'}
          busy={flow.busy}
          onConfirm={flow.confirm}
          onClose={flow.close}
        />
      )}
    </Screen>
  )
}

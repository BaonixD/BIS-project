import { AdminDocuments } from '@/components/documents/AdminDocuments'
import { dateFormatter } from '@/i18n/date'
import { t, useLocale } from '@/i18n/core'
import { APPROVAL_STATUS_LABELS } from '@/lib/labels'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { ArrowLeft, Check, CircleAlert } from 'lucide-react'
import { vehicleCategoryLabel, type NextAdminDriver } from '@/api/driver-types'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { FullScreenLoader } from '@/components/common/FullScreenLoader'
import { Avatar } from '@/components/driver/Avatar'
import { Button, KzPlate, StatusPill } from '@/components/ui-kit'
import { useAdminDriver } from '@/hooks/use-admin'
import { AdminLayout, RidesLink } from './admin-controls'
import { DRIVER_FIELD_LABELS } from '@/lib/labels'
import { CarClassSheet } from './CarClassSheet'
import { useApproveFlow } from './use-approve-flow'
const registeredFormat = () =>
  dateFormatter({
    timeZone: 'Asia/Almaty',
    day: 'numeric',
    month: 'long',
  })
function Facts({ rows }: { rows: [string, ReactNode][] }) {
  useLocale()
  return (
    <dl className="flex w-full flex-col gap-2.5 overflow-hidden rounded-lg bg-bg-canvas p-4 text-callout">
      {rows.map(([label, value]) => (
        <div key={label} className="flex w-full items-start gap-3">
          <dt className="min-w-0 flex-1 text-text-secondary">{label}</dt>
          <dd className="flex max-w-[60%] justify-end break-words text-right text-text-primary">
            {value}
          </dd>
        </div>
      ))}
    </dl>
  )
}
function DriverDetails({ driver }: { driver: NextAdminDriver }) {
  useLocale()
  const name = driver.full_name ?? driver.username
  const vehicle = driver.vehicle
  const vehicleRows: [string, ReactNode][] = [
    [t('Машина'), vehicle ? `${vehicle.make} ${vehicle.model}` : '—'],
    [t('Цвет'), vehicle?.color ?? '—'],
    [t('Госномер'), vehicle?.plate_number ? <KzPlate plate={vehicle.plate_number} /> : '—'],
  ]
  if (driver.approval_status === 'approved' && vehicle?.car_class) {
    vehicleRows.push([t('Принимает тарифы'), vehicleCategoryLabel(vehicle)])
  }
  const missing = driver.missing_fields.map((field) => DRIVER_FIELD_LABELS()[field] ?? field)
  return (
    <>
      <div className="flex w-full items-center gap-4">
        <Avatar name={name} size={64} />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <p className="truncate text-headline text-text-primary">{name}</p>
          <p className="truncate text-caption text-text-secondary">
            @{driver.username}
            {t(' · зарегистрирован')} {registeredFormat().format(new Date(driver.created_at))}
          </p>
        </div>
      </div>
      <Facts
        rows={[
          [t('Телефон'), driver.phone ?? '—'],
          [t('Права'), driver.license_number ?? '—'],
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
            ? t('Все обязательные поля заполнены')
            : t('Не заполнено: {p0}', { p0: missing.join(', ') })}
        </p>
      </div>
    </>
  )
}
/** Figma 26:764: a driver's application, in the common admin frame. */
export function AdminDriverPage() {
  useLocale()
  const { driverId } = useParams()
  const drivers = useAdminDriver(driverId)
  const flow = useApproveFlow()
  if (drivers.isPending) return <FullScreenLoader />
  const driver = drivers.data ?? null
  const approved = driver?.approval_status === 'approved'
  const submitted = driver ? ['pending', 'legacy'].includes(driver.documents_summary) : false
  const blocked = Boolean(driver?.blocked_at)
  const disabledReason = blocked
    ? t('Аккаунт заблокирован — сначала снимите блокировку.')
    : !approved && !submitted
      ? t('Водитель ещё не отправил документы на проверку.')
      : null
  return (
    <AdminLayout
      title={approved ? t('Водитель') : t('Заявка водителя')}
      description={t('Данные водителя, документы и допуск к работе.')}
      refreshing={drivers.isFetching}
      onRefresh={() => void drivers.refetch()}
    >
      <Link to="/admin?status=all" className="inline-flex items-center gap-2 self-start text-callout">
        <ArrowLeft className="size-4" aria-hidden />
        {t('Все водители')}
      </Link>
      <ErrorAlert error={drivers.error} />
      {driver ? (
        <div className="grid w-full items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <div className="flex min-w-0 flex-col gap-4">
            <DriverDetails driver={driver} />
            <section className="flex flex-col gap-3 rounded-lg bg-bg-canvas p-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-headline text-text-primary">{t('Допуск к работе')}</h2>
                <StatusPill tone={blocked ? 'danger' : approved ? 'success' : 'warning'}>
                  {blocked ? t('Аккаунт заблокирован') : APPROVAL_STATUS_LABELS()[driver.approval_status]}
                </StatusPill>
              </div>
              <p className="text-callout text-text-secondary">
                {approved
                  ? t('Водитель получает заказы своего класса и ниже. Класс можно изменить.')
                  : t('Проверьте документы и данные машины, затем одобрите и назначьте класс.')}
              </p>
              <Button
                size="md"
                className="w-full"
                disabled={disabledReason !== null}
                onClick={() => flow.open(driver)}
              >
                {approved ? t('Сменить класс машины') : t('Одобрить водителя')}
              </Button>
              {disabledReason && (
                <p className="text-caption text-text-secondary">{disabledReason}</p>
              )}
              <div className="flex flex-wrap gap-x-5 gap-y-2 pt-1">
                <RidesLink userId={driver.id} role="driver">
                  {t('Поездки водителя')}
                </RidesLink>
                <Link
                  to={`/admin/users/${driver.id}`}
                  className="text-callout underline underline-offset-4"
                >
                  {t('Блокировка и доступ')}
                </Link>
              </div>
            </section>
          </div>
          <AdminDocuments driverId={driver.id} />
        </div>
      ) : (
        !drivers.error && (
          <p className="text-callout text-text-secondary">{t('Водитель не найден')}</p>
        )
      )}
      {flow.target && (
        <CarClassSheet
          initial={flow.target.vehicle?.car_class ?? 'economy'}
          confirmLabel={approved ? t('Сохранить класс') : t('Одобрить')}
          busy={flow.busy}
          onConfirm={flow.confirm}
          onClose={flow.close}
        />
      )}
    </AdminLayout>
  )
}

import { documentStatusLabel } from '@/lib/document-labels'
import { t, useLocale } from '@/i18n/core'
import { ADMIN_PAGE_SIZE, useAdminFilters } from './admin-model'
import { Link } from 'react-router'
import { AlertCircle, ChevronRight } from 'lucide-react'
import type { ApprovalStatus } from '@/api'
import type { NextAdminDriver } from '@/api/driver-types'
import { TARIFF_LABELS, vehicleCategories } from '@/api/driver-types'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Avatar } from '@/components/driver/Avatar'
import { Button, Chip, StatusPill } from '@/components/ui-kit'
import { useAdminDrivers } from '@/hooks/use-admin'
import { vehicleLine } from './admin-format'
import { CarClassSheet } from './CarClassSheet'
import { useApproveFlow } from './use-approve-flow'
import {
  AdminEmpty,
  AdminLayout,
  AdminLoading,
  AdminResults,
  AdminSearch,
  AdminSelect,
} from './admin-controls'
const FILTERS = () =>
  [
    ['pending', t('На проверке')],
    ['approved', t('Одобрены')],
    ['all', t('Все')],
  ] as const
function DriverRequest({ driver, onApprove }: { driver: NextAdminDriver; onApprove: () => void }) {
  useLocale()
  const name = driver.full_name ?? driver.username
  return (
    <li className="flex flex-col gap-4 rounded-lg bg-bg-canvas p-5">
      <Link
        to={`/admin/drivers/${driver.id}`}
        className="flex items-center gap-3 outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
      >
        <Avatar name={name} size={48} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-body-medium text-text-primary">{name}</p>
          <p className="text-caption text-text-secondary">@{driver.username}</p>
        </div>
        <ChevronRight className="size-5 text-text-tertiary" />
      </Link>
      <div className="flex flex-wrap gap-2">
        <StatusPill
          tone={
            driver.blocked_at
              ? 'danger'
              : driver.approval_status === 'approved'
                ? 'success'
                : 'warning'
          }
        >
          {driver.blocked_at
            ? t('Заблокирован')
            : driver.approval_status === 'approved'
              ? t('Одобрен')
              : t('На проверке')}
        </StatusPill>
        <StatusPill tone={driver.online ? 'info' : 'neutral'}>
          {driver.online ? t('На линии') : t('Не на линии')}
        </StatusPill>
        {driver.vehicle &&
          vehicleCategories(driver.vehicle).map((category) => (
            <StatusPill key={category}>{TARIFF_LABELS()[category]}</StatusPill>
          ))}
      </div>
      <p className="text-caption text-text-secondary">{documentStatusLabel(driver.documents_summary)}</p>
      <p className="text-callout text-text-secondary">{vehicleLine(driver)}</p>
      {driver.missing_fields.length > 0 && (
        <p className="flex items-center gap-2 text-caption text-accent-danger">
          <AlertCircle className="size-4" />
          {t('Профиль заполнен не полностью')}
        </p>
      )}
      <div className="mt-auto grid grid-cols-2 gap-2">
        <Button asChild variant="secondary" size="md">
          <Link to={`/admin/drivers/${driver.id}`}>{t('Подробнее')}</Link>
        </Button>
        <Button size="md" onClick={onApprove} disabled={Boolean(driver.blocked_at)}>
          {driver.approval_status === 'approved' ? t('Класс машины') : t('Одобрить')}
        </Button>
      </div>
    </li>
  )
}
export function AdminDriversPage() {
  useLocale()
  const { params, offset, update, reset } = useAdminFilters()
  const status = params.get('status') ?? 'pending'
  const filter = status === 'approved' ? 'approved' : status === 'all' ? 'all' : 'pending'
  const q = params.get('q') ?? ''
  const documentFilter = params.get('documents') ?? ''
  const online = params.get('online')
  const drivers = useAdminDrivers(filter === 'all' ? undefined : (filter as ApprovalStatus), {
    limit: ADMIN_PAGE_SIZE,
    offset,
    q: q || undefined,
    online: online === 'true' ? true : online === 'false' ? false : undefined,
  })
  const waiting = useAdminDrivers('pending', { limit: 1 })
  const flow = useApproveFlow()
  return (
    <AdminLayout
      title={t('Водители')}
      description={t('Проверяйте заявки, назначайте класс машины и следите за доступностью.')}
      refreshing={drivers.isFetching}
      onRefresh={() => {
        void drivers.refetch()
        void waiting.refetch()
      }}
    >
      <div className="flex flex-wrap items-center gap-2">
        {FILTERS().map(([id, label]) => (
          <Chip key={id} selected={filter === id} onClick={() => update({ status: id })}>
            {label}
          </Chip>
        ))}
        {(waiting.data?.total ?? 0) > 0 && (
          <StatusPill tone="warning">
            {waiting.data!.total}
            {t(' ждут')}
          </StatusPill>
        )}
      </div>
      <div className="grid items-end gap-3 rounded-lg bg-bg-canvas p-4 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_160px_220px_auto]">
        <AdminSearch
          key={q}
          value={q}
          placeholder={t('Имя, логин, телефон или госномер')}
          onSearch={(value) => update({ q: value })}
        />
        <AdminSelect
          label={t('Доступность')}
          value={online ?? ''}
          options={[
            ['', t('Любая')],
            ['true', t('На линии')],
            ['false', t('Не на линии')],
          ]}
          onChange={(value) => update({ online: value })}
        />
        <AdminSelect label={t("Документы")} value={documentFilter} options={[["", t("Все")], ...["pending", "missing", "draft", "rejected", "approved", "legacy"].map((value) => [value, documentStatusLabel(value)] as const)]} onChange={(value) => update({ documents: value })} />
        <Button variant="ghost" size="md" onClick={reset}>
          {t('Сбросить')}
        </Button>
      </div>
      <ErrorAlert error={drivers.error} />
      {drivers.isPending && <AdminLoading />}
      {drivers.data?.items.length === 0 && <AdminEmpty onReset={reset} />}
      <ul
        className={`grid gap-4 md:grid-cols-2 xl:grid-cols-3 ${drivers.isPlaceholderData ? 'pointer-events-none opacity-50' : ''}`}
        aria-busy={drivers.isFetching}
      >
        {drivers.data?.items.map((driver) => (
          <DriverRequest key={driver.id} driver={driver} onApprove={() => flow.open(driver)} />
        ))}
      </ul>
      <AdminResults
        total={drivers.data?.total}
        offset={offset}
        busy={drivers.isFetching}
        onPage={(value) => update({ offset: String(value) }, true)}
      />
      {flow.target && (
        <CarClassSheet
          initial={flow.target.vehicle?.car_class ?? 'economy'}
          confirmLabel={
            flow.target.approval_status === 'approved' ? t('Сохранить класс') : t('Одобрить')
          }
          busy={flow.busy}
          onConfirm={flow.confirm}
          onClose={flow.close}
        />
      )}
    </AdminLayout>
  )
}

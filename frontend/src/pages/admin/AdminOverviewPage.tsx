import { t, useLocale } from '@/i18n/core'
import { Link } from 'react-router'
import { ArrowUpRight, Car, Clock, Users, Wallet } from 'lucide-react'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { useAdminDrivers, useAdminOverview } from '@/hooks/use-admin'
import { formatMoney } from '@/lib/format'
import { AdminLayout, AdminLoading } from './admin-controls'
export function AdminOverviewPage() {
  useLocale()
  const query = useAdminOverview()
  const waiting = useAdminDrivers('pending', { limit: 1, document_status: 'pending' })
  const data = query.data
  const metrics = data
    ? [
        {
          label: t('Ждут проверки'),
          value: waiting.data?.total ?? '—',
          icon: Clock,
          to: '/admin?status=pending&documents=pending',
          note: t('Водители с документами'),
        },
        {
          label: t('Активные поездки'),
          value: data.active_rides,
          icon: Car,
          to: '/admin/rides?view=active',
          note: t('От поиска до завершения'),
        },
        {
          label: t('Водители на линии'),
          value: data.online_drivers,
          icon: Car,
          to: '/admin?status=all&online=true',
          note: t('Включая занятых водителей'),
        },
        {
          label: t('Пользователи'),
          value: data.total_users,
          icon: Users,
          to: '/admin/users',
          note: t('{p0} заблокировано', { p0: data.blocked_users }),
        },
      ]
    : []
  return (
    <AdminLayout
      title={t('Обзор сервиса')}
      description={t('Что происходит сейчас и итоги за всё время. Данные обновляются сами.')}
      refreshing={query.isFetching}
      onRefresh={() => void query.refetch()}
    >
      <ErrorAlert error={query.error} />
      {query.isPending && <AdminLoading />}
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {metrics.map(({ label, value, icon: Icon, to, note }) => (
          <Link
            key={label}
            to={to}
            className="group rounded-lg bg-bg-canvas p-4 outline-none transition-shadow hover:shadow-card focus-visible:ring-2 focus-visible:ring-bg-inverse sm:p-5"
          >
            <div className="flex items-center justify-between text-text-secondary">
              <Icon className="size-5" />
              <ArrowUpRight className="size-4" />
            </div>
            <p className="mt-4 text-title text-text-primary sm:mt-5 sm:text-display">{value}</p>
            <p className="mt-1 text-body-medium text-text-primary">{label}</p>
            <p className="mt-1 text-caption text-text-secondary">{note}</p>
          </Link>
        ))}
      </div>
      {data && (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-lg bg-bg-canvas p-5">
            <h2 className="text-headline text-text-primary">{t('Результаты поездок')}</h2>
            <div className="mt-5 grid grid-cols-2 gap-4">
              <Link to="/admin/rides?view=completed" className="outline-none focus-visible:ring-2">
                <p className="text-display text-accent-success">{data.completed_rides}</p>
                <p className="text-callout text-text-secondary">{t('Завершено')}</p>
              </Link>
              <Link to="/admin/rides?view=cancelled" className="outline-none focus-visible:ring-2">
                <p className="text-display text-text-primary">{data.cancelled_rides}</p>
                <p className="text-callout text-text-secondary">{t('Отмена / нет водителя')}</p>
              </Link>
            </div>
          </section>
          <section className="rounded-lg bg-bg-canvas p-5">
            <div className="flex items-center gap-2">
              <Wallet className="size-5" />
              <h2 className="text-headline text-text-primary">{t('Оплата завершённых поездок')}</h2>
            </div>
            <p className="mt-4 text-display text-text-primary">{formatMoney(data.collected_kzt)}</p>
            <p className="text-caption text-text-secondary">
              {t('Получено за поездки. Kaspi — учебная оплата, реальные деньги не списываются.')}
            </p>
            <Link
              to="/admin/rides?view=completed&payment_status=unpaid&payment_method=cash"
              className="mt-4 inline-block text-callout underline underline-offset-4"
            >
              {t('Ожидают наличных: ')}
              {formatMoney(data.outstanding_cash_kzt)}
            </Link>
          </section>
        </div>
      )}
    </AdminLayout>
  )
}

import { Link } from 'react-router'
import { ArrowUpRight, Car, Clock, Users, Wallet } from 'lucide-react'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { useAdminOverview } from '@/hooks/use-admin'
import { formatMoney } from '@/lib/format'
import { AdminLayout, AdminLoading } from './admin-controls'

export function AdminOverviewPage() {
  const query = useAdminOverview()
  const data = query.data
  const metrics = data
    ? [
        {
          label: 'Ждут проверки',
          value: data.pending_drivers,
          icon: Clock,
          to: '/admin?status=pending',
          note: 'Заявки водителей',
        },
        {
          label: 'Активные поездки',
          value: data.active_rides,
          icon: Car,
          to: '/admin/rides?view=active',
          note: 'От поиска до завершения',
        },
        {
          label: 'Водители на линии',
          value: data.online_drivers,
          icon: Car,
          to: '/admin?status=all&online=true',
          note: 'Включая занятых водителей',
        },
        {
          label: 'Пользователи',
          value: data.total_users,
          icon: Users,
          to: '/admin/users',
          note: `${data.blocked_users} заблокировано`,
        },
      ]
    : []
  return (
    <AdminLayout
      title="Обзор сервиса"
      description="Текущее состояние и итоги за всё время. Обновление каждые 15 секунд."
      refreshing={query.isFetching}
      onRefresh={() => void query.refetch()}
    >
      <ErrorAlert error={query.error} />
      {query.isPending && <AdminLoading />}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(({ label, value, icon: Icon, to, note }) => (
          <Link
            key={label}
            to={to}
            className="group rounded-lg bg-bg-canvas p-5 outline-none transition-shadow hover:shadow-card focus-visible:ring-2 focus-visible:ring-bg-inverse"
          >
            <div className="flex items-center justify-between text-text-secondary">
              <Icon className="size-5" />
              <ArrowUpRight className="size-4" />
            </div>
            <p className="mt-5 text-display text-text-primary">{value}</p>
            <p className="mt-1 text-body-medium text-text-primary">{label}</p>
            <p className="mt-1 text-caption text-text-secondary">{note}</p>
          </Link>
        ))}
      </div>
      {data && (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-lg bg-bg-canvas p-5">
            <h2 className="text-headline text-text-primary">Результаты поездок</h2>
            <div className="mt-5 grid grid-cols-2 gap-4">
              <Link to="/admin/rides?view=completed" className="outline-none focus-visible:ring-2">
                <p className="text-display text-accent-success">{data.completed_rides}</p>
                <p className="text-callout text-text-secondary">Завершено</p>
              </Link>
              <Link to="/admin/rides?view=cancelled" className="outline-none focus-visible:ring-2">
                <p className="text-display text-text-primary">{data.cancelled_rides}</p>
                <p className="text-callout text-text-secondary">Отмена / нет водителя</p>
              </Link>
            </div>
          </section>
          <section className="rounded-lg bg-bg-canvas p-5">
            <div className="flex items-center gap-2">
              <Wallet className="size-5" />
              <h2 className="text-headline text-text-primary">Оплата завершённых поездок</h2>
            </div>
            <p className="mt-4 text-display text-text-primary">{formatMoney(data.collected_kzt)}</p>
            <p className="text-caption text-text-secondary">
              Подтверждённая оплата · Kaspi учитывается как учебная имитация
            </p>
            <Link
              to="/admin/rides?view=completed&payment_status=unpaid&payment_method=cash"
              className="mt-4 inline-block text-callout underline underline-offset-4"
            >
              Ожидают наличных: {formatMoney(data.outstanding_cash_kzt)}
            </Link>
          </section>
        </div>
      )}
    </AdminLayout>
  )
}

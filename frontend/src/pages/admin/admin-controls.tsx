import { useState, type ReactNode } from 'react'
import { Link, NavLink } from 'react-router'
import { ArrowUpRight, RefreshCw, Search } from 'lucide-react'
import { Button, Input, Skeleton } from '@/components/ui-kit'
import { Pagination } from '@/components/common/Pagination'
import { AdminLogoutButton } from './AdminLogoutButton'
import { ADMIN_PAGE_SIZE } from './admin-model'

export function AdminLayout({
  title,
  description,
  children,
  refreshing,
  onRefresh,
}: {
  title: string
  description: string
  children: ReactNode
  refreshing?: boolean
  onRefresh: () => void
}) {
  return (
    <div className="min-h-dvh bg-bg-subtle">
      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pt-[calc(64px+env(safe-area-inset-top))] pb-8 lg:gap-5 lg:px-8 lg:pt-8">
        <header className="flex items-start justify-between gap-4 sm:items-center">
          <div className="min-w-0">
            <p className="mb-1 text-label text-text-secondary">BIS TAXI / УПРАВЛЕНИЕ</p>
            <h1 className="text-display text-text-primary">{title}</h1>
            <p className="mt-1 text-callout text-text-secondary">{description}</p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <Button
              variant="ghost"
              size="md"
              onClick={onRefresh}
              disabled={refreshing}
              aria-label="Обновить данные"
            >
              <RefreshCw className={refreshing ? 'motion-safe:animate-spin' : ''} />
              <span className="hidden sm:inline">Обновить</span>
            </Button>
            <AdminLogoutButton />
          </div>
        </header>
        <nav aria-label="Управление сервисом" className="flex gap-2 overflow-x-auto pb-1">
          {(
            [
              ['/admin/overview', 'Обзор'],
              ['/admin', 'Водители'],
              ['/admin/rides', 'Поездки'],
              ['/admin/users', 'Пользователи'],
            ] as const
          ).map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/admin'}
              className={({ isActive }) =>
                `shrink-0 rounded-full px-4 py-2.5 text-callout outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse ${isActive ? 'bg-bg-inverse text-text-inverse' : 'bg-bg-canvas text-text-secondary'}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
        {children}
      </div>
    </div>
  )
}

export function AdminSearch({
  value,
  placeholder,
  onSearch,
}: {
  value: string
  placeholder: string
  onSearch: (value: string) => void
}) {
  const [draft, setDraft] = useState(value)
  return (
    <form
      className="flex min-w-0 w-full flex-col gap-1.5"
      onSubmit={(event) => {
        event.preventDefault()
        onSearch(draft.trim())
      }}
      role="search"
    >
      <span className="text-caption text-text-secondary">Поиск</span>
      <div className="flex min-w-0 items-center gap-2">
        <Input
          icon={Search}
          placeholder={placeholder}
          aria-label={placeholder}
          value={draft}
          maxLength={100}
          onChange={(event) => setDraft(event.target.value)}
          containerClassName="h-11 min-w-0 border border-border-default bg-bg-canvas px-3 [&>svg]:size-5 focus-within:border"
          className="text-callout"
        />
        <Button type="submit" size="md">
          Найти
        </Button>
      </div>
    </form>
  )
}

export function AdminSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: readonly (readonly [string, string])[]
  onChange: (value: string) => void
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1.5 text-caption text-text-secondary">
      <span>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full rounded-md border border-border-default bg-bg-canvas px-3 text-callout text-text-primary outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
      >
        {options.map(([id, text]) => (
          <option key={id} value={id}>
            {text}
          </option>
        ))}
      </select>
    </label>
  )
}

export function AdminResults({
  total,
  offset,
  busy,
  onPage,
}: {
  total?: number
  offset: number
  busy: boolean
  onPage: (offset: number) => void
}) {
  return (
    <div className="flex flex-col gap-2" aria-busy={busy}>
      <p className="text-caption text-text-secondary" role="status">
        {total === undefined
          ? 'Загружаем…'
          : total === 0
            ? 'Найдено: 0'
            : `${offset + 1}–${Math.min(offset + ADMIN_PAGE_SIZE, total)} из ${total}`}
      </p>
      <div className={busy ? 'pointer-events-none opacity-50' : ''}>
        {total !== undefined && (
          <Pagination offset={offset} limit={ADMIN_PAGE_SIZE} total={total} onChange={onPage} />
        )}
      </div>
    </div>
  )
}

export function AdminEmpty({
  message = 'Ничего не найдено',
  onReset,
}: {
  message?: string
  onReset: () => void
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg bg-bg-canvas px-5 py-10 text-center sm:py-12">
      <p className="text-headline text-text-primary">{message}</p>
      <p className="text-callout text-text-secondary">
        Попробуйте другой запрос или измените фильтры.
      </p>
      <Button variant="secondary" size="md" onClick={onReset}>
        Сбросить фильтры
      </Button>
    </div>
  )
}

export function AdminLoading() {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Skeleton className="h-40 rounded-lg" />
      <Skeleton className="h-40 rounded-lg" />
    </div>
  )
}

export function FactList({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="flex flex-col divide-y divide-border-default">
      {items.map(([label, value]) => (
        <div
          key={label}
          className="flex flex-wrap items-start justify-between gap-2 py-3 text-callout"
        >
          <dt className="text-text-secondary">{label}</dt>
          <dd className="min-w-0 max-w-full break-words text-right text-text-primary">
            {value ?? '—'}
          </dd>
        </div>
      ))}
    </dl>
  )
}

export function RidesLink({
  userId,
  role,
  children = 'Поездки пользователя',
}: {
  userId: string
  role: string
  children?: ReactNode
}) {
  return (
    <Link
      className="inline-flex items-center gap-1 text-callout text-text-primary underline underline-offset-4 outline-none focus-visible:ring-2"
      to={`/admin/rides?view=all&${role === 'driver' ? 'driver_id' : 'passenger_id'}=${userId}`}
    >
      {children}
      <ArrowUpRight className="size-4" aria-hidden />
    </Link>
  )
}

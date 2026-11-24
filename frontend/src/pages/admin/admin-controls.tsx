import { ThemeToggle } from '@/components/common/ThemeToggle'
import { TitleOrnament } from '@/components/common/Ornament'
import { LanguageSwitcher } from '@/i18n/LanguageSwitcher'
import { t, useLocale } from '@/i18n/core'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { ArrowUpRight, Check, Copy, RefreshCw, Search } from 'lucide-react'
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
  useLocale()
  return (
    <div className="min-h-dvh bg-bg-subtle">
      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pt-[calc(16px+env(safe-area-inset-top))] pb-8 lg:gap-5 lg:px-8 lg:pt-8">
        <div className="flex items-center justify-end gap-1 lg:hidden">
          <ThemeToggle className="text-text-primary hover:bg-bg-muted" />
          <LanguageSwitcher />
          <AdminLogoutButton />
        </div>
        <header className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-title text-text-primary sm:text-display">{title}</h1>
            <TitleOrnament className="mt-2" />
            <p className="mt-2 max-w-2xl text-callout text-text-secondary">{description}</p>
          </div>
          <Button
            variant="ghost"
            size="md"
            className="shrink-0"
            onClick={onRefresh}
            disabled={refreshing}
            aria-label={t('Обновить данные')}
          >
            <RefreshCw className={refreshing ? 'motion-safe:animate-spin' : ''} />
            <span className="hidden sm:inline">{t('Обновить')}</span>
          </Button>
        </header>
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
  useLocale()
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
      <span className="text-caption text-text-secondary">{t('Поиск')}</span>
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
          {t('Найти')}
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
  useLocale()
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
  useLocale()
  return (
    <div className="flex flex-col gap-2" aria-busy={busy}>
      <p
        className={total === 0 ? 'sr-only' : 'text-caption text-text-secondary'}
        role="status"
      >
        {total === undefined
          ? t('Загружаем…')
          : total === 0
            ? t('Найдено: 0')
            : t('{p0}–{p1} из {p2}', {
                p0: offset + 1,
                p1: Math.min(offset + ADMIN_PAGE_SIZE, total),
                p2: total,
              })}
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
  message = t('Ничего не найдено'),
  text = t('Попробуйте другой запрос или измените фильтры.'),
  action,
  onReset,
}: {
  message?: string
  text?: string
  /** A next step instead of «Сбросить фильтры», e.g. «Показать всех водителей». */
  action?: { label: string; onClick: () => void }
  onReset: () => void
}) {
  useLocale()
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg bg-bg-canvas px-5 py-10 text-center sm:py-12">
      <p className="text-headline text-text-primary">{message}</p>
      <p className="max-w-md text-callout text-text-secondary">{text}</p>
      <Button variant="secondary" size="md" onClick={action?.onClick ?? onReset}>
        {action?.label ?? t('Сбросить фильтры')}
      </Button>
    </div>
  )
}
export function AdminLoading() {
  useLocale()
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Skeleton className="h-40 rounded-lg" />
      <Skeleton className="h-40 rounded-lg" />
    </div>
  )
}
export function FactList({ items }: { items: [string, ReactNode][] }) {
  useLocale()
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
  children = t('Поездки пользователя'),
}: {
  userId: string
  role: string
  children?: ReactNode
}) {
  useLocale()
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

/** A long identifier shown short, with a button that copies it whole. */
export function CopyId({ value }: { value: string }) {
  useLocale()
  const [copied, setCopied] = useState(false)
  return (
    <span className="inline-flex items-center gap-2">
      <span className="font-mono text-caption text-text-secondary" title={value}>
        {value.slice(0, 8)}…
      </span>
      <button
        type="button"
        onClick={() => {
          void navigator.clipboard?.writeText(value).then(() => {
            setCopied(true)
            window.setTimeout(() => setCopied(false), 1500)
          })
        }}
        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-caption text-text-primary outline-none hover:bg-bg-muted focus-visible:ring-2 focus-visible:ring-bg-inverse"
      >
        {copied ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
        {copied ? t('Скопировано') : t('Копировать')}
      </button>
    </span>
  )
}

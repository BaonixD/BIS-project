import { Globe } from 'lucide-react'
import { cn } from '@/lib/utils'
import { setLocale, t, useLocale, type Locale } from './core'

export function LanguageSwitcher({
  inverse = false,
  className,
}: {
  inverse?: boolean
  className?: string
}) {
  const locale = useLocale()
  return (
    <label
      className={cn(
        'inline-flex h-10 shrink-0 items-center gap-2 rounded-md border px-2.5',
        inverse
          ? 'border-white/30 text-text-inverse'
          : 'border-border-default bg-bg-canvas text-text-primary',
        className,
      )}
    >
      <Globe className="size-4 shrink-0" aria-hidden />
      <span className="sr-only">{t('Язык интерфейса')}</span>
      <select
        value={locale}
        onChange={(event) => setLocale(event.target.value as Locale)}
        className="min-w-0 cursor-pointer bg-transparent text-callout outline-none focus-visible:ring-2 focus-visible:ring-accent-success"
        aria-label={t('Язык интерфейса')}
      >
        <option value="ru" lang="ru" className="bg-bg-canvas text-text-primary">
          Русский
        </option>
        <option value="kk" lang="kk" className="bg-bg-canvas text-text-primary">
          Қазақша
        </option>
        <option value="en" lang="en" className="bg-bg-canvas text-text-primary">
          English
        </option>
      </select>
    </label>
  )
}

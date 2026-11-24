import { Moon, Sun, SunMoon } from 'lucide-react'
import { t, useLocale } from '@/i18n/core'
import { cn } from '@/lib/utils'
import { setMapTheme, useMapThemeChoice, type MapThemeChoice } from '@/lib/map-theme'

const OPTIONS = () =>
  [
    ['auto', SunMoon, t('Авто')],
    ['day', Sun, t('День')],
    ['night', Moon, t('Ночь')],
  ] as const satisfies readonly (readonly [MapThemeChoice, typeof Sun, string])[]

/** Map look: «Түнгі Алматы» at night (auto: 20:00–6:00 Almaty time), or fixed day or night. */
export function MapThemeSwitch({ className }: { className?: string }) {
  useLocale()
  const choice = useMapThemeChoice()
  return (
    <div className={cn('flex w-full flex-col gap-2 rounded-lg bg-bg-canvas p-4', className)}>
      <div className="flex flex-col gap-0.5">
        <p className="text-body-medium text-text-primary">{t('Карта')}</p>
        <p className="text-caption text-text-secondary">
          {t('«Түнгі Алматы» — тёмная карта с золотыми магистралями; в режиме «Авто» с 20:00 до 6:00.')}
        </p>
      </div>
      <div role="radiogroup" aria-label={t('Карта')} className="grid grid-cols-3 gap-1 rounded-xl bg-bg-subtle p-1">
        {OPTIONS().map(([id, Icon, label]) => (
          <button
            key={id}
            type="button"
            role="radio"
            aria-checked={choice === id}
            onClick={() => setMapTheme(id)}
            className={cn(
              'flex h-10 items-center justify-center gap-1.5 rounded-lg text-callout outline-none transition-colors focus-visible:ring-2 focus-visible:ring-bg-inverse',
              choice === id ? 'bg-bg-canvas text-brand-sky-ink shadow-card' : 'text-text-secondary',
            )}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}

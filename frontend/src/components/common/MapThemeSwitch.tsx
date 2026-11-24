import { Monitor, Moon, Sun, SunMoon } from 'lucide-react'
import { t, useLocale } from '@/i18n/core'
import { cn } from '@/lib/utils'
import { setMapTheme, useMapThemeChoice, type MapThemeChoice } from '@/lib/map-theme'
import { setTheme, useThemeChoice, type ThemeChoice } from '@/lib/theme'

const THEME_OPTIONS = () =>
  [
    ['system', Monitor, t('Системная')],
    ['light', Sun, t('Светлая')],
    ['dark', Moon, t('Тёмная')],
  ] as const satisfies readonly (readonly [ThemeChoice, typeof Sun, string])[]

function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: T
  options: readonly (readonly [T, typeof Sun, string])[]
  onChange: (value: T) => void
}) {
  return (
    <div role="radiogroup" aria-label={label} className="grid grid-cols-3 gap-1 rounded-xl bg-bg-subtle p-1">
      {options.map(([id, Icon, text]) => (
        <button
          key={id}
          type="button"
          role="radio"
          aria-checked={value === id}
          onClick={() => onChange(id)}
          className={cn(
            'flex h-10 items-center justify-center gap-1.5 rounded-lg text-callout outline-none transition-colors focus-visible:ring-2 focus-visible:ring-bg-inverse',
            value === id ? 'bg-bg-canvas text-brand-sky-ink shadow-card' : 'text-text-secondary',
          )}
        >
          <Icon className="size-4" aria-hidden />
          {text}
        </button>
      ))}
    </div>
  )
}

/** Theme of the whole app and the map look, kept on this device. */
export function AppearanceSettings({ className }: { className?: string }) {
  useLocale()
  const theme = useThemeChoice()
  const map = useMapThemeChoice()
  return (
    <div className={cn('flex w-full flex-col gap-4 rounded-lg bg-bg-canvas p-4', className)}>
      <div className="flex flex-col gap-2">
        <p className="text-body-medium text-text-primary">{t('Оформление')}</p>
        <Segmented label={t('Оформление')} value={theme} options={THEME_OPTIONS()} onChange={setTheme} />
      </div>
      <div className="flex flex-col gap-2">
        <div className="flex flex-col gap-0.5">
          <p className="text-body-medium text-text-primary">{t('Карта')}</p>
          <p className="text-caption text-text-secondary">
            {t('«Түнгі Алматы» — тёмная карта с золотыми магистралями; «Авто» включает её ночью и в тёмной теме.')}
          </p>
        </div>
        <Segmented label={t('Карта')} value={map} options={OPTIONS()} onChange={setMapTheme} />
      </div>
    </div>
  )
}

const OPTIONS = () =>
  [
    ['auto', SunMoon, t('Авто')],
    ['day', Sun, t('День')],
    ['night', Moon, t('Ночь')],
  ] as const satisfies readonly (readonly [MapThemeChoice, typeof Sun, string])[]

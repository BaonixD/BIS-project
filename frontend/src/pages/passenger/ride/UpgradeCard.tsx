import { useState } from 'react'
import { ArrowRight, Gift, Sparkles } from 'lucide-react'
import type { RideDetails } from '@/api'
import type { Tariff } from '@/api/passenger-types'
import carImage from '@/assets/car.png'
import { KazakhMotif } from '@/components/common/Ornament'
import { Button, showToast } from '@/components/ui-kit'
import { useRideUpgrades, useUpgradeRide } from '@/hooks/use-bonuses'
import { t, useLocale } from '@/i18n/core'
import { cn } from '@/lib/utils'
import { formatPrice } from '@/pages/passenger/model/format'
import { TARIFF_LABELS } from '@/pages/passenger/model/order'

/** The flag's sun: a disc with 32 rays, drawn once. */
const RAYS = Array.from({ length: 32 }, (_, index) => {
  const angle = (index * Math.PI * 2) / 32
  const point = (radius: number, shift = 0) =>
    `${(50 + radius * Math.cos(angle + shift)).toFixed(2)},${(50 + radius * Math.sin(angle + shift)).toFixed(2)}`
  return `M${point(27, -0.06)}L${point(46)}L${point(27, 0.06)}Z`
}).join('')

function FlagSun({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" aria-hidden className={className}>
      <g fill="currentColor">
        <path d={RAYS} />
        <circle cx="50" cy="50" r="22" />
      </g>
    </svg>
  )
}

/** A car gliding from the current class to the chosen one. */
function ClassShift({ from, to }: { from: Tariff; to: Tariff }) {
  return (
    <div className="flex items-center gap-2" aria-hidden>
      <span className="shrink-0 text-caption text-text-secondary line-through decoration-text-tertiary">
        {TARIFF_LABELS()[from]}
      </span>
      <span className="relative h-7 min-w-0 flex-1">
        <span className="absolute inset-x-0 top-1/2 border-t border-dashed border-brand-sky-ink/40" />
        <img
          src={carImage}
          alt=""
          draggable={false}
          className="absolute top-0 left-[calc(50%-22px)] h-7 w-11 object-contain mix-blend-multiply motion-safe:animate-car-glide"
        />
      </span>
      <ArrowRight className="size-4 shrink-0 text-brand-sky-ink" />
      <span key={to} className="shrink-0 text-callout text-text-primary motion-safe:animate-fade-up">
        {TARIFF_LABELS()[to]}
      </span>
    </div>
  )
}

/** While searching: raise the tariff for the difference, optionally with bonuses. */
export function UpgradeCard({ ride }: { ride: RideDetails }) {
  useLocale()
  const upgrades = useRideUpgrades(ride.id, ride.status === 'searching')
  const upgrade = useUpgradeRide(ride.id)
  const [chosen, setChosen] = useState<Tariff | null>(null)
  const [useBonus, setUseBonus] = useState(false)
  const options = upgrades.data?.tariff === ride.tariff ? upgrades.data.options : []
  if (options.length === 0) return null
  const option = options.find((item) => item.tariff === chosen) ?? options[0]!
  const bonus = useBonus ? option.bonus_kzt : 0
  const surcharge = Math.max(0, option.surcharge_kzt - bonus)
  const submit = () =>
    upgrade.mutate(
      { tariff: option.tariff, useBonus: useBonus && option.bonus_kzt > 0 },
      {
        onSuccess: () => {
          setChosen(null)
          setUseBonus(false)
          showToast({
            title: t('Тариф повышен до «{p0}»', { p0: TARIFF_LABELS()[option.tariff] }),
          })
        },
      },
    )
  return (
    <section
      aria-label={t('Повысить класс')}
      className="relative w-full overflow-hidden rounded-[20px] border border-brand-sky/30 bg-linear-to-br from-[#e9f8fb] via-[#dff3f7] to-[#fdf4d6] p-4 motion-safe:animate-fade-up"
    >
      <FlagSun className="pointer-events-none absolute -top-10 -right-10 size-32 text-brand-gold/70 motion-safe:animate-sun-spin" />
      <KazakhMotif className="pointer-events-none absolute right-3 bottom-2 h-10 w-[52px] text-brand-sky-ink/10" />
      <div className="relative flex flex-col gap-3">
        <div className="flex flex-col gap-0.5 pr-16">
          <p className="inline-flex items-center gap-1.5 text-label tracking-wide text-brand-sky-ink uppercase">
            <Sparkles className="size-3.5" aria-hidden />
            {t('Повысить класс')}
          </p>
          <p className="text-callout text-text-secondary">
            {t('Доплатите разницу — поиск продолжится среди машин выбранного класса.')}
          </p>
        </div>
        <div role="radiogroup" aria-label={t('Тариф')} className="flex gap-2 overflow-x-auto scrollbar-none">
          {options.map((item) => (
            <button
              key={item.tariff}
              type="button"
              role="radio"
              aria-checked={item.tariff === option.tariff}
              onClick={() => setChosen(item.tariff)}
              className={cn(
                'flex shrink-0 flex-col items-start rounded-xl border px-3 py-2 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-bg-inverse',
                item.tariff === option.tariff
                  ? 'border-brand-sky-ink bg-bg-canvas shadow-card'
                  : 'border-transparent bg-bg-canvas/60',
              )}
            >
              <span className="text-callout text-text-primary">{TARIFF_LABELS()[item.tariff]}</span>
              <span className="text-caption text-text-secondary">
                +{formatPrice(item.surcharge_kzt)}
              </span>
            </button>
          ))}
        </div>
        <ClassShift from={ride.tariff} to={option.tariff} />
        {option.bonus_kzt > 0 && (
          <label className="flex cursor-pointer items-center gap-2 text-callout text-text-primary">
            <input
              type="checkbox"
              checked={useBonus}
              onChange={(event) => setUseBonus(event.target.checked)}
              className="size-4 accent-[var(--color-brand-sky-ink)]"
            />
            <Gift className="size-4 text-text-secondary" aria-hidden />
            {t('Оплатить бонусами до {p0}', { p0: formatPrice(option.bonus_kzt) })}
          </label>
        )}
        {upgrade.error && (
          <p role="alert" className="text-caption text-accent-danger">
            {t('Не удалось повысить класс: водитель уже мог принять заказ.')}
          </p>
        )}
        <Button size="md" className="w-full" loading={upgrade.isPending} onClick={submit}>
          {surcharge > 0
            ? t('Улучшить до «{p0}» · +{p1}', {
                p0: TARIFF_LABELS()[option.tariff],
                p1: formatPrice(surcharge),
              })
            : t('Улучшить до «{p0}» бонусами', { p0: TARIFF_LABELS()[option.tariff] })}
        </Button>
      </div>
    </section>
  )
}

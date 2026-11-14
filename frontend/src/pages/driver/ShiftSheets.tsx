import { t, useLocale } from '@/i18n/core'
import { Link } from 'react-router'
import { Car, User } from 'lucide-react'
import type { NextDriver } from '@/api/driver-types'
import { Button, ListRow } from '@/components/ui-kit'
import { formatMoney } from '@/lib/format'
import { formatSpan, type ShiftStats } from './shift-stats'
function Stat({ value, label }: { value: string; label: string }) {
  useLocale()
  return (
    <div className="flex flex-col gap-0.5">
      <p className="text-headline whitespace-nowrap text-text-primary">{value}</p>
      <p className="text-caption whitespace-nowrap text-text-secondary">{label}</p>
    </div>
  )
}
/** Figma Stats (6:78, 25:229): rides and earnings for today plus approval or time online. */
export function ShiftStatsCard({
  stats,
  third,
}: {
  stats: ShiftStats
  third: {
    value: string
    label: string
  }
}) {
  useLocale()
  return (
    <div className="flex w-full items-center justify-between overflow-hidden rounded-lg bg-bg-subtle p-4">
      <Stat value={String(stats.rides)} label={t('поездок сегодня')} />
      <Stat value={formatMoney(stats.earnedKzt)} label={t('заработано')} />
      <Stat {...third} />
    </div>
  )
}
function SheetHeading({ title, text }: { title: string; text: string }) {
  useLocale()
  return (
    <>
      <h1 className="w-full text-title text-text-primary">{title}</h1>
      <p className="w-full text-body text-text-secondary">{text}</p>
    </>
  )
}
/** Figma 6:2: offline, approved. */
export function OfflineSheet({ stats }: { stats: ShiftStats }) {
  useLocale()
  return (
    <>
      <SheetHeading
        title={t('Готовы к заказам?')}
        text={t(
          'Выйдите на линию — мы будем предлагать ближайшие заказы. Местоположение обновляется автоматически.',
        )}
      />
      <ShiftStatsCard stats={stats} third={{ value: t('Одобрен'), label: t('допуск') }} />
    </>
  )
}
/** Figma 25:149: online, waiting for an offer. */
export function OnlineSheet({
  stats,
  onlineS,
  manualHint,
  leaving,
  onLeave,
  categories,
  onChooseCategories,
}: {
  stats: ShiftStats
  onlineS: number
  manualHint: boolean
  leaving: boolean
  onLeave: () => void
  categories: string
  onChooseCategories: () => void
}) {
  useLocale()
  return (
    <>
      <SheetHeading
        title={t('Ищем заказы рядом')}
        text={
          manualHint
            ? t(
                'Геолокация недоступна — нажмите на карту, где вы находитесь. Предложение появится здесь — на ответ будет 30 секунд.',
              )
            : t(
                'Предложение появится здесь — на ответ будет 30 секунд. Местоположение обновляется каждые 10 секунд.',
              )
        }
      />
      <ShiftStatsCard stats={stats} third={{ value: formatSpan(onlineS), label: t('на линии') }} />
      <div className="flex w-full flex-col gap-1">
        <p className="text-caption text-text-secondary">{t('Принимаете заказы')}</p>
        <p className="text-callout text-text-primary">{categories}</p>
      </div>
      <Button
        variant="ghost"
        size="md"
        className="w-full"
        disabled={leaving}
        onClick={onChooseCategories}
      >
        {t('Изменить тарифы')}
      </Button>
      <Button variant="secondary" className="w-full" loading={leaving} onClick={onLeave}>
        {t('Уйти с линии')}
      </Button>
    </>
  )
}
const PROFILE_FIELDS = ['full_name', 'phone', 'license_number']
/** Figma 25:2: account under review; what is filled in. */
export function PendingSheet({ driver }: { driver: NextDriver }) {
  useLocale()
  const profileDone = !driver.missing_fields.some((field) => PROFILE_FIELDS.includes(field))
  const vehicleDone = !driver.missing_fields.includes('vehicle')
  return (
    <>
      <SheetHeading
        title={t('Почти готово')}
        text={t(
          'Администратор проверяет данные. Заполните профиль и машину полностью, чтобы ускорить проверку.',
        )}
      />
      <div className="flex w-full flex-col">
        <ListRow
          icon={User}
          title={profileDone ? t('Профиль заполнен') : t('Заполните профиль')}
          subtitle={t('ФИО, телефон, права')}
          trailing={profileDone ? '✓' : ''}
        />
        <ListRow
          icon={Car}
          title={vehicleDone ? t('Машина') : t('Добавьте машину')}
          subtitle={t('Марка, цвет, госномер')}
          trailing={vehicleDone ? '✓' : ''}
        />
      </div>
      <Button asChild variant="secondary" className="w-full">
        <Link to="/driver/settings">{t('Открыть профиль')}</Link>
      </Button>
    </>
  )
}

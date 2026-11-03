import { Link } from 'react-router'
import { Car, User } from 'lucide-react'
import type { NextDriver } from '@/api/driver-types'
import { Button, ListRow } from '@/components/ui-kit'
import { formatMoney } from '@/lib/format'
import { formatSpan, type ShiftStats } from './shift-stats'

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <p className="text-headline whitespace-nowrap text-text-primary">{value}</p>
      <p className="text-caption whitespace-nowrap text-text-secondary">{label}</p>
    </div>
  )
}

/** Figma Stats (6:78, 25:229): rides and earnings for today plus approval or time online. */
export function ShiftStatsCard({ stats, third }: { stats: ShiftStats; third: { value: string; label: string } }) {
  return (
    <div className="flex w-full items-center justify-between overflow-hidden rounded-lg bg-bg-subtle p-4">
      <Stat value={String(stats.rides)} label="поездок сегодня" />
      <Stat value={formatMoney(stats.earnedKzt)} label="заработано" />
      <Stat {...third} />
    </div>
  )
}

function SheetHeading({ title, text }: { title: string; text: string }) {
  return (
    <>
      <h1 className="w-full text-title text-text-primary">{title}</h1>
      <p className="w-full text-body text-text-secondary">{text}</p>
    </>
  )
}

/** Figma 6:2: offline, approved. */
export function OfflineSheet({ stats }: { stats: ShiftStats }) {
  return (
    <>
      <SheetHeading
        title="Готовы к заказам?"
        text="Выйдите на линию — мы будем предлагать ближайшие заказы. Местоположение обновляется автоматически."
      />
      <ShiftStatsCard stats={stats} third={{ value: 'Одобрен', label: 'допуск' }} />
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
}: {
  stats: ShiftStats
  onlineS: number
  manualHint: boolean
  leaving: boolean
  onLeave: () => void
}) {
  return (
    <>
      <SheetHeading
        title="Ищем заказы рядом"
        text={
          manualHint
            ? 'Геолокация недоступна — нажмите на карту, где вы находитесь. Предложение появится здесь — на ответ будет 30 секунд.'
            : 'Предложение появится здесь — на ответ будет 30 секунд. Местоположение обновляется каждые 10 секунд.'
        }
      />
      <ShiftStatsCard stats={stats} third={{ value: formatSpan(onlineS), label: 'на линии' }} />
      <Button variant="secondary" className="w-full" loading={leaving} onClick={onLeave}>
        Уйти с линии
      </Button>
    </>
  )
}

const PROFILE_FIELDS = ['full_name', 'phone', 'license_number']

/** Figma 25:2: account under review; what is filled in. */
export function PendingSheet({ driver }: { driver: NextDriver }) {
  const profileDone = !driver.missing_fields.some((field) => PROFILE_FIELDS.includes(field))
  const vehicleDone = !driver.missing_fields.includes('vehicle')
  return (
    <>
      <SheetHeading
        title="Почти готово"
        text="Администратор проверяет данные. Заполните профиль и машину полностью, чтобы ускорить проверку."
      />
      <div className="flex w-full flex-col">
        <ListRow
          icon={User}
          title={profileDone ? 'Профиль заполнен' : 'Заполните профиль'}
          subtitle="ФИО, телефон, права"
          trailing={profileDone ? '✓' : ''}
        />
        <ListRow
          icon={Car}
          title={vehicleDone ? 'Машина' : 'Добавьте машину'}
          subtitle="Марка, цвет, госномер"
          trailing={vehicleDone ? '✓' : ''}
        />
      </div>
      <Button asChild variant="secondary" className="w-full">
        <Link to="/driver/settings">Открыть профиль</Link>
      </Button>
    </>
  )
}

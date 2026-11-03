import { Banknote, Car, Check, CreditCard, Navigation, Phone, Wallet, X } from 'lucide-react'
import type { DriverCard, RideDetails } from '@/api'
import {
  ProgressBar,
  RideDriverCard,
  RoundAction,
  RouteRows,
  StatusHeading,
  SummaryRows,
} from '@/components/passenger/ride-parts'
import { driverLine } from '@/components/passenger/ride-text'
import { Button, StatusPill } from '@/components/ui-kit'
import {
  elapsedShare,
  formatClock,
  formatCountdown,
  formatKm,
  formatPrice,
  pickupEtaMinutes,
} from '@/pages/passenger/model/format'
import { cancelText, dropoffCaption, paymentLine } from './ride-text'

/** The dispatcher looks for a driver for up to 3 minutes (SEARCH_BUDGET_S). */
export const SEARCH_BUDGET_S = 180
/** Free waiting after «Водитель на месте». */
export const FREE_WAIT_S = 180

interface SheetProps {
  ride: RideDetails
  now: number
}

function Price({ ride }: { ride: RideDetails }) {
  return <>{formatPrice(ride.amount_kzt)}</>
}

/** Figma Searching 5:337 and «Водитель отказался — ищем другого» 23:359. */
export function SearchingSheet({ ride, now, declinedAt, onCancel }: SheetProps & { declinedAt: number | null; onCancel: () => void }) {
  const since = declinedAt ? new Date(declinedAt).toISOString() : ride.created_at
  return (
    <>
      <StatusPill tone="inverse">Ищем водителя</StatusPill>
      <h1 className="w-full text-title text-text-primary">
        {declinedAt ? 'Подбираем другого водителя' : 'Подбираем ближайшего водителя'}
      </h1>
      {!declinedAt && (
        <p className="w-full text-body text-text-secondary">
          Предлагаем заказ водителям рядом по очереди — каждому 30 секунд. Обычно это занимает до 3 минут.
        </p>
      )}
      <ProgressBar value={elapsedShare(since, SEARCH_BUDGET_S, now)} label="Поиск водителя" />
      <RouteRows
        pickup={ride.pickup}
        dropoff={ride.dropoff}
        dropoffSubtitle={dropoffCaption(ride, { searching: true })}
        trailing={<Price ride={ride} />}
      />
      <Button variant="danger" className="w-full" onClick={onCancel}>
        Отменить поездку
      </Button>
    </>
  )
}

function etaText(ride: RideDetails, driver: DriverCard): string | null {
  return driver.location ? `~${pickupEtaMinutes(driver.location, ride.pickup)} мин` : null
}

/** Figma 23:256 «Водитель найден — оплата прошла» (Kaspi, shown once). */
export function DriverFoundSheet({
  ride,
  driver,
  onTrack,
  onReceipt,
}: {
  ride: RideDetails
  driver: DriverCard
  onTrack: () => void
  onReceipt: () => void
}) {
  const price = formatPrice(ride.amount_kzt)
  return (
    <>
      <StatusHeading
        icon={Check}
        tone="success"
        title="Водитель найден"
        text={`${price} списано через Kaspi в момент назначения. Это учебная оплата — реальные деньги не списываются.`}
      />
      <SummaryRows
        className="gap-2.5 rounded-lg bg-bg-subtle p-4"
        rows={[
          ['Водитель', driverLine(driver)],
          ['Подача', etaText(ride, driver) ?? '—'],
          ['Оплата', `Kaspi · ${price}`],
        ]}
      />
      <p className="flex w-full items-center gap-2.5 text-callout text-text-secondary">
        <span aria-hidden className="size-2.5 shrink-0 rounded-full bg-accent-success" />
        Водитель уже едет к вам
      </p>
      <Button className="w-full" onClick={onTrack}>
        Где мой водитель?
      </Button>
      <Button variant="ghost" size="md" className="w-full" onClick={onReceipt}>
        Открыть чек
      </Button>
    </>
  )
}

function osmDirections(ride: RideDetails, driver: DriverCard): string {
  const from = driver.location ?? ride.pickup
  return `https://www.openstreetmap.org/directions?route=${from.latitude},${from.longitude};${ride.pickup.latitude},${ride.pickup.longitude}`
}

/** Figma Driver on the way 5:444. */
export function OnTheWaySheet({ ride, driver, onCancel }: { ride: RideDetails; driver: DriverCard; onCancel: () => void }) {
  const eta = etaText(ride, driver)
  return (
    <>
      <div className="flex w-full flex-col items-start gap-1">
        <StatusPill tone="success">Водитель едет</StatusPill>
        <h1 className="w-full text-title text-text-primary">{eta ? `Приедет через ${eta}` : 'Водитель едет к вам'}</h1>
      </div>
      <RideDriverCard driver={driver} tariff={ride.tariff} />
      <div className="flex w-full items-center justify-between px-6">
        <RoundAction icon={Phone} label="Позвонить" href={driver.phone ? `tel:${driver.phone}` : undefined} />
        <RoundAction icon={Navigation} label="Маршрут" href={osmDirections(ride, driver)} />
        <RoundAction icon={X} label="Отменить" onClick={onCancel} />
      </div>
      <RouteRows pickup={ride.pickup} dropoff={ride.dropoff} dropoffSubtitle={dropoffCaption(ride)} trailing={<Price ride={ride} />} />
    </>
  )
}

/** Figma 24:424 «Водитель на месте». */
export function ArrivedSheet({ ride, driver, now, onCancel }: SheetProps & { driver: DriverCard; onCancel: () => void }) {
  const waited = ride.arrived_at ? (now - Date.parse(ride.arrived_at)) / 1000 : 0
  const left = FREE_WAIT_S - waited
  return (
    <>
      <div className="flex w-full flex-col items-start gap-1">
        <StatusPill tone="success">Водитель на месте</StatusPill>
        <h1 className="w-full text-title text-text-primary">Выходите — вас ждут</h1>
        <p className="w-full text-callout text-text-secondary">
          {left > 0 ? `Бесплатное ожидание · ${formatCountdown(left)}` : 'Бесплатное ожидание закончилось'}
        </p>
      </div>
      <RideDriverCard driver={driver} tariff={ride.tariff} />
      <div className="flex w-full items-center gap-3">
        <Button variant="secondary" className="min-w-0 flex-1" asChild={Boolean(driver.phone)} disabled={!driver.phone}>
          {driver.phone ? <a href={`tel:${driver.phone}`}>Позвонить</a> : 'Позвонить'}
        </Button>
        <Button variant="danger" className="min-w-0 flex-1" onClick={onCancel}>
          Отменить
        </Button>
      </div>
    </>
  )
}

/** Figma 24:525 «В пути». */
export function InProgressSheet({ ride, driver, now }: SheetProps & { driver: DriverCard | null }) {
  const { distance_m, duration_s } = ride.route
  const share = elapsedShare(ride.started_at, duration_s, now)
  const arrival = ride.started_at ? Date.parse(ride.started_at) + duration_s * 1000 : now + duration_s * 1000
  const minutesLeft = Math.max(1, Math.round((duration_s * (1 - share)) / 60))
  const PayIcon = ride.payment_method === 'cash' ? Banknote : CreditCard
  return (
    <>
      <div className="flex w-full flex-col items-start gap-1">
        <StatusPill tone="info">В пути</StatusPill>
        <h1 className="w-full text-title text-text-primary">Прибытие ~{formatClock(arrival)}</h1>
        <p className="w-full text-callout text-text-secondary">
          Осталось {formatKm(distance_m * (1 - share))} · около {minutesLeft} мин
        </p>
      </div>
      <ProgressBar value={share} label="Пройдено" />
      {driver && <RideDriverCard driver={driver} tariff={ride.tariff} />}
      <div className="flex w-full items-center gap-2.5 text-callout text-text-primary">
        <PayIcon className="size-6 shrink-0" strokeWidth={2} aria-hidden />
        <p className="min-w-0 flex-1">{paymentLine(ride)}</p>
        <p className="shrink-0 whitespace-nowrap">{formatPrice(ride.amount_kzt)}</p>
      </div>
    </>
  )
}

/** Figma 24:620 «Отменить поездку?». */
export function CancelConfirmSheet({
  ride,
  pending,
  error,
  onConfirm,
  onClose,
}: {
  ride: RideDetails
  pending: boolean
  error: string | null
  onConfirm: () => void
  onClose: () => void
}) {
  return (
    <>
      <StatusHeading icon={X} size={64} iconClassName="text-accent-danger" title="Отменить поездку?" text={cancelText(ride)} />
      {error && (
        <p role="alert" className="w-full text-caption text-accent-danger">
          {error}
        </p>
      )}
      <Button variant="danger" className="w-full" loading={pending} onClick={onConfirm}>
        Да, отменить
      </Button>
      <Button variant="secondary" className="w-full" disabled={pending} onClick={onClose}>
        {ride.status === 'searching' ? 'Нет, продолжить поиск' : 'Нет, жду водителя'}
      </Button>
    </>
  )
}

/** Figma 23:455 «Водитель не найден». */
export function NoDriverSheet({ ride, onRetry, onEditRoute }: { ride: RideDetails; onRetry: () => void; onEditRoute: () => void }) {
  const refunded = ride.payment_status === 'refunded'
  return (
    <>
      <StatusHeading
        icon={Car}
        title="Свободных водителей нет"
        text="Мы искали 3 минуты, но рядом никого не нашлось. Попробуйте ещё раз чуть позже."
      />
      <div className="flex w-full items-center gap-3 rounded-lg bg-bg-subtle p-4 text-left">
        <Wallet className="size-6 shrink-0 text-text-primary" strokeWidth={2} aria-hidden />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <p className="text-body-medium text-text-primary">{refunded ? 'Деньги вернутся' : 'Деньги не списаны'}</p>
          <p className="text-caption text-text-secondary">
            {refunded ? 'Оплата Kaspi возвращена автоматически' : 'Оплата проходит только когда найден водитель'}
          </p>
        </div>
        <StatusPill tone="info">{refunded ? formatPrice(ride.amount_kzt) : formatPrice(0)}</StatusPill>
      </div>
      <Button className="w-full" onClick={onRetry}>
        Искать снова
      </Button>
      <Button variant="ghost" size="md" className="w-full" onClick={onEditRoute}>
        Изменить маршрут
      </Button>
    </>
  )
}

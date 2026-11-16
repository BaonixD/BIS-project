import { t, useLocale } from '@/i18n/core'
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
import { elapsedShare, formatCountdown, formatPrice } from '@/pages/passenger/model/format'
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
  useLocale()
  return <>{formatPrice(ride.amount_kzt)}</>
}
/** Figma Searching 5:337 and «Водитель отказался — ищем другого» 23:359. */
export function SearchingSheet({
  ride,
  now,
  declinedAt,
  onCancel,
}: SheetProps & {
  declinedAt: number | null
  onCancel: () => void
}) {
  useLocale()
  const since = declinedAt ? new Date(declinedAt).toISOString() : ride.created_at
  return (
    <>
      <StatusPill tone="inverse">{t('Ищем водителя')}</StatusPill>
      <h1 className="w-full text-title text-text-primary">
        {declinedAt ? t('Подбираем другого водителя') : t('Подбираем ближайшего водителя')}
      </h1>
      {!declinedAt && (
        <p className="w-full text-body text-text-secondary">
          {t(
            'Предлагаем заказ водителям рядом по очереди — каждому 30 секунд. Обычно это занимает до 3 минут.',
          )}
        </p>
      )}
      <ProgressBar value={elapsedShare(since, SEARCH_BUDGET_S, now)} label={t('Поиск водителя')} />
      <RouteRows
        pickup={ride.pickup}
        dropoff={ride.dropoff}
        dropoffSubtitle={dropoffCaption(ride, { searching: true })}
        trailing={<Price ride={ride} />}
      />
      <Button variant="danger" className="w-full" onClick={onCancel}>
        {t('Отменить поездку')}
      </Button>
    </>
  )
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
  useLocale()
  const price = formatPrice(ride.amount_kzt)
  return (
    <>
      <StatusHeading
        icon={Check}
        tone="success"
        title={t('Водитель найден')}
        text={t(
          '{p0} списано через Kaspi в момент назначения. Это учебная оплата — реальные деньги не списываются.',
          { p0: price },
        )}
      />
      <SummaryRows
        className="gap-2.5 rounded-lg bg-bg-subtle p-4"
        rows={[
          [t('Водитель'), driverLine(driver)],
          [t('Оплата'), `Kaspi · ${price}`],
        ]}
      />
      <p className="flex w-full items-center gap-2.5 text-callout text-text-secondary">
        <span aria-hidden className="size-2.5 shrink-0 rounded-full bg-accent-success" />
        {t('Водитель уже едет к вам')}
      </p>
      <Button className="w-full" onClick={onTrack}>
        {t('Где мой водитель?')}
      </Button>
      <Button variant="ghost" size="md" className="w-full" onClick={onReceipt}>
        {t('Открыть чек')}
      </Button>
    </>
  )
}
function osmDirections(ride: RideDetails, driver: DriverCard): string {
  const from = driver.location ?? ride.pickup
  return `https://www.openstreetmap.org/directions?route=${from.latitude},${from.longitude};${ride.pickup.latitude},${ride.pickup.longitude}`
}
/** Figma Driver on the way 5:444. */
export function OnTheWaySheet({
  ride,
  driver,
  onCancel,
}: {
  ride: RideDetails
  driver: DriverCard
  onCancel: () => void
}) {
  useLocale()
  return (
    <>
      <div className="flex w-full flex-col items-start gap-1">
        <StatusPill tone="success">{t('Водитель едет')}</StatusPill>
        <h1 className="w-full text-title text-text-primary">{t('Водитель едет к вам')}</h1>
      </div>
      <RideDriverCard driver={driver} tariff={ride.tariff} />
      <div className="flex w-full items-center justify-between px-6">
        <RoundAction
          icon={Phone}
          label={t('Позвонить')}
          href={driver.phone ? `tel:${driver.phone}` : undefined}
        />
        <RoundAction icon={Navigation} label={t('Маршрут')} href={osmDirections(ride, driver)} />
        <RoundAction icon={X} label={t('Отменить')} onClick={onCancel} />
      </div>
      <RouteRows
        pickup={ride.pickup}
        dropoff={ride.dropoff}
        dropoffSubtitle={dropoffCaption(ride)}
        trailing={<Price ride={ride} />}
      />
    </>
  )
}
/** Figma 24:424 «Водитель на месте». */
export function ArrivedSheet({
  ride,
  driver,
  now,
  onCancel,
}: SheetProps & {
  driver: DriverCard
  onCancel: () => void
}) {
  useLocale()
  const waited = ride.arrived_at ? (now - Date.parse(ride.arrived_at)) / 1000 : 0
  const left = FREE_WAIT_S - waited
  return (
    <>
      <div className="flex w-full flex-col items-start gap-1">
        <StatusPill tone="success">{t('Водитель на месте')}</StatusPill>
        <h1 className="w-full text-title text-text-primary">{t('Выходите — вас ждут')}</h1>
        <p className="w-full text-callout text-text-secondary">
          {left > 0
            ? t('Бесплатное ожидание · {p0}', { p0: formatCountdown(left) })
            : t('Бесплатное ожидание закончилось')}
        </p>
      </div>
      <RideDriverCard driver={driver} tariff={ride.tariff} />
      <div className="flex w-full items-center gap-3">
        <Button
          variant="secondary"
          className="min-w-0 flex-1"
          asChild={Boolean(driver.phone)}
          disabled={!driver.phone}
        >
          {driver.phone ? <a href={`tel:${driver.phone}`}>{t('Позвонить')}</a> : t('Позвонить')}
        </Button>
        <Button variant="danger" className="min-w-0 flex-1" onClick={onCancel}>
          {t('Отменить')}
        </Button>
      </div>
    </>
  )
}
/** Figma 24:525 «В пути». */
export function InProgressSheet({
  ride,
  driver,
}: SheetProps & {
  driver: DriverCard | null
}) {
  useLocale()
  const PayIcon = ride.payment_method === 'cash' ? Banknote : CreditCard
  return (
    <>
      <div className="flex w-full flex-col items-start gap-1">
        <StatusPill tone="info">{t('В пути')}</StatusPill>
        <h1 className="w-full text-title text-text-primary">{t('До места назначения')}</h1>
      </div>
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
  useLocale()
  return (
    <>
      <StatusHeading
        icon={X}
        size={64}
        iconClassName="text-accent-danger"
        title={t('Отменить поездку?')}
        text={cancelText(ride)}
      />
      {error && (
        <p role="alert" className="w-full text-caption text-accent-danger">
          {error}
        </p>
      )}
      <Button variant="danger" className="w-full" loading={pending} onClick={onConfirm}>
        {t('Да, отменить')}
      </Button>
      <Button variant="secondary" className="w-full" disabled={pending} onClick={onClose}>
        {ride.status === 'searching' ? t('Нет, продолжить поиск') : t('Нет, жду водителя')}
      </Button>
    </>
  )
}
/** Figma 23:455 «Водитель не найден». */
export function NoDriverSheet({
  ride,
  onRetry,
  onEditRoute,
}: {
  ride: RideDetails
  onRetry: () => void
  onEditRoute: () => void
}) {
  useLocale()
  const refunded = ride.payment_status === 'refunded'
  return (
    <>
      <StatusHeading
        icon={Car}
        title={t('Свободных водителей нет')}
        text={t('Мы искали 3 минуты, но рядом никого не нашлось. Попробуйте ещё раз чуть позже.')}
      />
      <div className="flex w-full items-center gap-3 rounded-lg bg-bg-subtle p-4 text-left">
        <Wallet className="size-6 shrink-0 text-text-primary" strokeWidth={2} aria-hidden />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <p className="text-body-medium text-text-primary">
            {refunded ? t('Деньги вернутся') : t('Деньги не списаны')}
          </p>
          <p className="text-caption text-text-secondary">
            {refunded
              ? t('Оплата Kaspi возвращена автоматически')
              : t('Оплата проходит только когда найден водитель')}
          </p>
        </div>
        <StatusPill tone="info">
          {refunded ? formatPrice(ride.amount_kzt) : formatPrice(0)}
        </StatusPill>
      </div>
      <Button className="w-full" onClick={onRetry}>
        {t('Искать снова')}
      </Button>
      <Button variant="ghost" size="md" className="w-full" onClick={onEditRoute}>
        {t('Изменить маршрут')}
      </Button>
    </>
  )
}

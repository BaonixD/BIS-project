import { t, useLocale } from '@/i18n/core'
import { useState } from 'react'
import { User, X } from 'lucide-react'
import { errorMessage } from '@/api'
import type { NextRide } from '@/api/driver-types'
import { BottomSheet, Button, Chip, showToast, StatusIcon, Stepper } from '@/components/ui-kit'
import { useDriverRideCommand, useReleaseRide, type DriverRideCommand } from '@/hooks/use-rides'
import { paymentSummary, RIDE_STEPS, rideStep } from './driver-screen'
import { buildReleaseBody, RELEASE_REASONS, type ReleaseReason } from './release'
const NEXT_COMMAND = (): Partial<
  Record<
    NextRide['status'],
    {
      command: DriverRideCommand
      label: string
    }
  >
> => ({
  assigned: { command: 'arrive', label: t('Я на месте') },
  arrived: { command: 'start', label: t('Начать поездку') },
  in_progress: { command: 'complete', label: t('Завершить поездку') },
})
/** Figma Passenger row (6:321): the API has no passenger name or phone. */
export function PassengerRow({ ride }: { ride: NextRide }) {
  useLocale()
  return (
    <div className="flex w-full items-center gap-3">
      <span className="flex size-12 shrink-0 items-center justify-center rounded-full bg-bg-muted">
        <User className="size-6 text-text-primary" strokeWidth={2} aria-hidden />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <p className="text-headline text-text-primary">{t('Пассажир')}</p>
        <p className="truncate text-caption text-text-secondary">{paymentSummary(ride)}</p>
      </div>
    </div>
  )
}
/** Figma 6:243 / 25:260 / 25:359: passenger, progress, the next command and the way out. */
export function RideSheet({ ride, onRelease }: { ride: NextRide; onRelease: () => void }) {
  useLocale()
  const command = useDriverRideCommand(ride.id)
  const next = NEXT_COMMAND()[ride.status]
  const releasable = ride.status === 'assigned' || ride.status === 'arrived'
  return (
    <>
      <PassengerRow ride={ride} />
      <Stepper steps={RIDE_STEPS()} current={rideStep(ride.status)} />
      {next && (
        <Button
          className="w-full"
          loading={command.isPending}
          onClick={() =>
            command.mutate(next.command, {
              onError: (error) => showToast({ title: errorMessage(error) }),
            })
          }
        >
          {next.label}
        </Button>
      )}
      {releasable && (
        <Button variant="ghost" size="md" className="w-full" onClick={onRelease}>
          {t('Отказаться от заказа')}
        </Button>
      )}
    </>
  )
}
/** Figma 25:497: release with a reason; the order goes back to the search. */
export function ReleaseSheet({
  ride,
  onClose,
  onReleased,
}: {
  ride: NextRide
  onClose: () => void
  onReleased: () => void
}) {
  useLocale()
  const release = useReleaseRide(ride.id)
  const [reason, setReason] = useState<ReleaseReason | null>(null)
  const [comment, setComment] = useState('')
  const submit = () => {
    if (!reason) return
    release.mutate(buildReleaseBody(reason, comment).reason, {
      onSuccess: onReleased,
      onError: (error) => showToast({ title: errorMessage(error) }),
    })
  }
  return (
    <>
      <div aria-hidden className="absolute inset-0 z-10 bg-black/40" onClick={onClose} />
      <BottomSheet role="dialog" aria-modal aria-label={t('Отказаться от заказа')} className="pb-7">
        <h2 className="w-full text-title text-text-primary">{t('Отказаться от заказа?')}</h2>
        <p className="w-full text-callout text-text-secondary">
          {t('Заказ вернётся в поиск, вам его больше не предложат. Укажите причину.')}
        </p>
        <div aria-label={t('Причина')} className="flex w-full flex-wrap items-center gap-2">
          {RELEASE_REASONS.map((item) => (
            <Chip key={item} selected={reason === item} onClick={() => setReason(item)}>
              {t(item)}
            </Chip>
          ))}
        </div>
        <textarea
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          maxLength={200}
          placeholder={t('Комментарий (необязательно)')}
          aria-label={t('Комментарий')}
          className="h-[88px] w-full shrink-0 resize-none rounded-md bg-bg-subtle p-4 text-body text-text-primary outline-none placeholder:text-text-secondary focus-visible:ring-2 focus-visible:ring-bg-inverse"
        />
        <Button
          variant="danger"
          className="w-full"
          disabled={!reason}
          loading={release.isPending}
          onClick={submit}
        >
          {t('Отказаться')}
        </Button>
        <Button variant="ghost" size="md" className="w-full" onClick={onClose}>
          {t('Вернуться к заказу')}
        </Button>
      </BottomSheet>
    </>
  )
}
/** Figma 26:425: the passenger cancelled. */
export function CancelledSheet({ online, onDismiss }: { online: boolean; onDismiss: () => void }) {
  useLocale()
  return (
    <BottomSheet centered aria-label={t('Поездка отменена')} className="gap-[18px]">
      <StatusIcon icon={X} size={64} />
      <div className="flex w-full flex-col gap-1.5">
        <h2 className="text-title text-text-primary">{t('Пассажир отменил поездку')}</h2>
        <p className="text-callout text-text-secondary">
          {online
            ? t('Вы снова на линии — следующий заказ придёт автоматически')
            : t('Заказ закрыт — выйдите на линию, чтобы получать новые')}
        </p>
      </div>
      <Button className="w-full" onClick={onDismiss}>
        {t('Понятно')}
      </Button>
    </BottomSheet>
  )
}

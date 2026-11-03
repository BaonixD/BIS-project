import { useState } from 'react'
import { Banknote, Check, CircleDot, MapPin } from 'lucide-react'
import { errorMessage } from '@/api'
import { PASSENGER_TAG_LABELS, PASSENGER_TAGS, type NextRide, type PassengerTag } from '@/api/driver-types'
import { Screen, ScreenColumn, ScreenFooter } from '@/components/driver/Screen'
import { Button, ListRow, RatingStars, showToast, StatusPill, Tag } from '@/components/ui-kit'
import { buildRatingBody, useRatePassenger } from '@/hooks/use-driver-rating'
import { useReverseGeocode } from '@/hooks/use-geocoding'
import { useConfirmCashReceived } from '@/hooks/use-payment'
import { formatDistance, formatDuration, formatMoney } from '@/lib/format'
import { cn } from '@/lib/utils'

function Heading({ title, text }: { title: string; text: string }) {
  return (
    <div className="flex w-full flex-col items-center gap-1.5 text-center">
      <h1 className="w-full text-title text-text-primary">{title}</h1>
      <p className="w-full text-callout text-text-secondary">{text}</p>
    </div>
  )
}

function AmountCard({ label, amount, pill, className }: { label: string; amount: number; pill: React.ReactNode; className?: string }) {
  return (
    <div className={cn('flex w-full flex-col items-center gap-1 overflow-hidden rounded-[20px] bg-bg-canvas px-5 text-center', className)}>
      <p className="text-callout text-text-secondary">{label}</p>
      <p className="text-[44px] leading-[52px] font-bold tracking-[-0.5px] whitespace-nowrap text-text-primary">
        {formatMoney(amount)}
      </p>
      {pill}
    </div>
  )
}

/** Figma 13:442: a completed cash ride — confirm the money. */
export function CollectCashScreen({ ride }: { ride: NextRide }) {
  const confirm = useConfirmCashReceived(ride.id)
  const pickup = useReverseGeocode(ride.pickup)
  const dropoff = useReverseGeocode(ride.dropoff)
  return (
    <Screen tone="subtle" overNav>
      <ScreenColumn className="items-center gap-5 pt-[calc(72px+env(safe-area-inset-top))] pb-32">
        <span className="flex size-18 shrink-0 items-center justify-center rounded-full bg-bg-inverse text-text-inverse">
          <Banknote className="size-6" strokeWidth={2} aria-hidden />
        </span>
        <Heading title="Получите оплату" text="Пассажир платит наличными. Подтвердите, когда получите деньги." />
        <AmountCard
          label="Сумма"
          amount={ride.amount_kzt}
          className="py-5"
          pill={<StatusPill tone="warning">Ожидает оплаты</StatusPill>}
        />
        <div className="flex w-full flex-col overflow-hidden rounded-[20px] bg-bg-canvas p-2">
          <ListRow icon={CircleDot} title={pickup.data?.title ?? 'Точка подачи'} subtitle="Откуда" />
          <ListRow
            icon={MapPin}
            title={dropoff.data?.title ?? 'Точка назначения'}
            subtitle={`Куда · ${formatDistance(ride.route.distance_m)} · ${formatDuration(ride.route.duration_s)}`}
          />
        </div>
      </ScreenColumn>
      <ScreenFooter>
        <Button
          className="w-full"
          loading={confirm.isPending}
          onClick={() => confirm.mutate(undefined, { onError: (error) => showToast({ title: errorMessage(error) }) })}
        >
          Наличные получены
        </Button>
      </ScreenFooter>
    </Screen>
  )
}

/** Figma 25:464: the ride is paid (Kaspi at assignment, or cash just confirmed); rate the passenger. */
export function CompletedScreen({
  ride,
  paidBy,
  onDone,
}: {
  ride: NextRide
  paidBy: 'kaspi' | 'cash'
  onDone: () => void
}) {
  const rate = useRatePassenger(ride.id)
  const [stars, setStars] = useState(5)
  const [tags, setTags] = useState<Set<PassengerTag>>(() => new Set())

  const toggle = (tag: PassengerTag, selected: boolean) =>
    setTags((current) => {
      const next = new Set(current)
      if (selected) next.add(tag)
      else next.delete(tag)
      return next
    })

  const submit = () =>
    rate.mutate(buildRatingBody(stars, tags), {
      onSuccess: onDone,
      onError: (error) => showToast({ title: errorMessage(error) }),
    })

  return (
    <Screen tone="subtle" overNav>
      <ScreenColumn className="items-center gap-4 pt-[calc(100px+env(safe-area-inset-top))] pb-40">
        <span className="flex size-14 shrink-0 items-center justify-center rounded-full bg-accent-success text-text-inverse">
          <Check className="size-8" strokeWidth={2} aria-hidden />
        </span>
        <Heading
          title="Поездка завершена"
          text={
            paidBy === 'kaspi'
              ? 'Kaspi списан при назначении — получать деньги не нужно'
              : 'Наличные получены — поездка оплачена'
          }
        />
        <AmountCard
          label="Ваш заработок"
          amount={ride.amount_kzt}
          className="py-4"
          pill={<StatusPill tone="success">{paidBy === 'kaspi' ? 'Оплачено Kaspi' : 'Получено наличными'}</StatusPill>}
        />
        <div className="flex w-full flex-col items-center gap-3 overflow-hidden rounded-[20px] bg-bg-canvas p-4">
          <p className="text-[15px] leading-5 font-semibold text-text-primary">Оцените пассажира</p>
          <RatingStars value={stars} onChange={setStars} label="Оценка пассажира" />
          <div className="flex flex-wrap items-start justify-center gap-1.5">
            {PASSENGER_TAGS.map((tag) => (
              <Tag key={tag} selected={tags.has(tag)} onSelectedChange={(selected) => toggle(tag, selected)}>
                {PASSENGER_TAG_LABELS[tag]}
              </Tag>
            ))}
          </div>
        </div>
      </ScreenColumn>
      <ScreenFooter className="pb-[calc(40px+env(safe-area-inset-bottom))]">
        <button
          type="button"
          onClick={onDone}
          className="text-callout text-text-secondary outline-none focus-visible:underline"
        >
          Пропустить
        </button>
        <Button className="w-full" loading={rate.isPending} onClick={submit}>
          Оценить и к новым заказам
        </Button>
      </ScreenFooter>
    </Screen>
  )
}

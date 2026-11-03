import { useState, type ReactNode } from 'react'
import { Banknote, Check, X } from 'lucide-react'
import type { DriverCard, RideDetails } from '@/api'
import { FullScreen } from '@/components/passenger/layout'
import { StatusHeading, SummaryRows } from '@/components/passenger/ride-parts'
import { driverLine, usePlaceTitle } from '@/components/passenger/ride-text'
import { Button, RatingStars, StatusIcon, StatusPill, Tag, type StatusTone } from '@/components/ui-kit'
import { useRateRide } from '@/hooks/use-rides'
import { cn } from '@/lib/utils'
import { passengerErrorMessage } from '@/pages/passenger/model/errors'
import { formatKm, formatMinutes, formatPrice, withName } from '@/pages/passenger/model/format'
import { TARIFF_LABELS } from '@/pages/passenger/model/order'
import { COMPACT_RATING_TAGS, RATING_TAG_LABELS, buildRating, toggleTag } from '@/pages/passenger/model/rating'
import type { PassengerRatingTag } from '@/api/passenger-types'

/** Grey full-screen result page with a footer pinned to the bottom (Figma 5:499, 24:633, 24:668). */
function ResultPage({ children, footer, top }: { children: ReactNode; footer: ReactNode; top: string }) {
  return (
    <FullScreen className="bg-bg-subtle">
      <div className={cn('mx-auto flex min-h-full w-full max-w-[420px] flex-col px-4', top)}>
        <div className="flex w-full flex-col items-center">{children}</div>
        <div className="mt-auto flex w-full flex-col items-center gap-3 pt-6">{footer}</div>
      </div>
    </FullScreen>
  )
}

function Receipt({
  label,
  amount,
  pill,
  rows,
  className,
}: {
  label: string
  amount: number
  pill: { tone: StatusTone; text: string }
  rows: [string, ReactNode][]
  className?: string
}) {
  return (
    <section className={cn('flex w-full flex-col gap-3 bg-bg-canvas', className)}>
      <div className="flex w-full items-center gap-3">
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <p className="text-callout text-text-secondary">{label}</p>
          <p className="text-display text-text-primary">{formatPrice(amount)}</p>
        </div>
        <StatusPill tone={pill.tone}>{pill.text}</StatusPill>
      </div>
      {rows.length > 0 && <SummaryRows rows={rows} />}
    </section>
  )
}

function Divider() {
  return <div className="h-px w-full bg-border-default" />
}

function tripLine(ride: RideDetails): string {
  return `${formatMinutes(ride.route.duration_s)} · ${formatKm(ride.route.distance_m)}`
}

/** Figma 24:668 «Поездка завершена (наличные)»: waits for the driver to confirm the cash. */
export function PayCashScreen({ ride, driver, onDone }: { ride: RideDetails; driver: DriverCard | null; onDone: () => void }) {
  const price = formatPrice(ride.amount_kzt)
  const driverRow: [string, ReactNode][] = driver ? [['Водитель', driverLine(driver)]] : []
  return (
    <ResultPage
      top="pt-[49px] pb-[34px]"
      footer={
        <Button variant="secondary" className="w-full" onClick={onDone}>
          Готово
        </Button>
      }
    >
      <div className="flex w-full flex-col items-center gap-5">
        <StatusHeading
          icon={Banknote}
          iconClassName="bg-accent-warning text-text-primary"
          gap="gap-5"
          title="Оплатите наличными"
          text={`Передайте водителю ${price}. Он подтвердит получение — статус обновится сам.`}
        />
        <section className="flex w-full flex-col gap-3 rounded-lg bg-bg-canvas p-5">
          <Receipt label="К оплате" amount={ride.amount_kzt} pill={{ tone: 'warning', text: 'Ожидает' }} rows={[]} />
          <Divider />
          <SummaryRows rows={[['Тариф', TARIFF_LABELS[ride.tariff]], ...driverRow, ['Время', tripLine(ride)]]} />
        </section>
      </div>
    </ResultPage>
  )
}

function RatingCard({
  ride,
  driver,
  stars,
  tags,
  comment,
  commentOpen,
  onStars,
  onTags,
  onComment,
  onOpenComment,
}: {
  ride: RideDetails
  driver: DriverCard | null
  stars: number
  tags: PassengerRatingTag[]
  comment: string
  commentOpen: boolean
  onStars: (stars: number) => void
  onTags: (tags: PassengerRatingTag[]) => void
  onComment: (comment: string) => void
  onOpenComment: () => void
}) {
  const rated = ride.my_rating
  return (
    <section className="flex w-full flex-col items-center gap-3 rounded-[20px] bg-bg-canvas px-4 pt-4 pb-3.5">
      <h2 className="text-[15px] leading-5 font-semibold text-text-primary">
        {rated ? 'Ваша оценка' : driver ? `Оцените поездку ${withName(driver.full_name)}` : 'Оцените поездку'}
      </h2>
      <RatingStars value={rated ? rated.stars : stars} onChange={onStars} readOnly={Boolean(rated)} />
      {rated ? (
        rated.tags.length > 0 && (
          <p className="text-center text-caption text-text-secondary">
            {rated.tags.map((tag) => RATING_TAG_LABELS[tag as PassengerRatingTag] ?? tag).join(' · ')}
          </p>
        )
      ) : (
        <>
          <div className="flex flex-wrap items-start justify-center gap-1.5">
            {COMPACT_RATING_TAGS.map(({ tag, label }) => (
              <Tag key={tag} selected={tags.includes(tag)} onSelectedChange={() => onTags(toggleTag(tags, tag))}>
                {label}
              </Tag>
            ))}
          </div>
          {commentOpen ? (
            <textarea
              aria-label="Комментарий"
              value={comment}
              maxLength={500}
              rows={2}
              autoFocus
              onChange={(event) => onComment(event.target.value)}
              placeholder="Что понравилось или нет"
              className="w-full resize-none rounded-md bg-bg-subtle px-3 py-2 text-callout text-text-primary outline-none placeholder:text-text-secondary focus:ring-2 focus:ring-bg-inverse"
            />
          ) : (
            <button type="button" onClick={onOpenComment} className="text-caption text-text-secondary">
              + Комментарий
            </button>
          )}
        </>
      )}
    </section>
  )
}

/** Figma 5:499 «Поездка завершена»: receipt and the compact rating. */
export function CompletedScreen({
  ride,
  driver,
  onDone,
}: {
  ride: RideDetails
  driver: DriverCard | null
  onDone: (message?: string) => void
}) {
  const rate = useRateRide(ride.id)
  const destination = usePlaceTitle(ride.dropoff)
  const [stars, setStars] = useState(0)
  const [tags, setTags] = useState<PassengerRatingTag[]>([])
  const [comment, setComment] = useState('')
  const [commentOpen, setCommentOpen] = useState(false)
  const kaspi = ride.payment_method === 'kaspi_link'
  const driverRow: [string, ReactNode][] = driver ? [['Водитель', driverLine(driver)]] : []

  const submit = () =>
    rate.mutate(buildRating(stars, tags, comment), { onSuccess: () => onDone('Спасибо за оценку') })

  return (
    <ResultPage
      top="pt-[61px] pb-10"
      footer={
        ride.my_rating ? (
          <Button className="w-full" onClick={() => onDone()}>
            Готово
          </Button>
        ) : (
          <>
            {rate.error && (
              <p role="alert" className="text-caption text-accent-danger">
                {passengerErrorMessage(rate.error)}
              </p>
            )}
            <button type="button" onClick={() => onDone()} className="text-callout text-text-secondary">
              Пропустить
            </button>
            <Button className="w-full" disabled={stars === 0} loading={rate.isPending} onClick={submit}>
              Отправить оценку
            </Button>
          </>
        )
      }
    >
      <div className="flex w-full flex-col items-center gap-[18px]">
        <StatusIcon icon={Check} tone="success" size={64} className="[&_svg]:size-6" />
        <div className="flex w-full flex-col items-center gap-1.5 text-center">
          <h1 className="w-full text-title text-text-primary">Поездка завершена</h1>
          <p className="w-full text-callout text-text-secondary">
            {[destination, tripLine(ride)].filter(Boolean).join(' · ')}
          </p>
        </div>
        <section className="flex w-full flex-col gap-3 rounded-[20px] bg-bg-canvas px-5 py-[18px]">
          <Receipt label="Итого" amount={ride.amount_kzt} pill={{ tone: 'success', text: 'Оплачено' }} rows={[]} />
          <Divider />
          <SummaryRows rows={[['Способ', kaspi ? 'Kaspi · списано при назначении' : 'Наличные · водителю'], ...driverRow]} />
        </section>
        <RatingCard
          ride={ride}
          driver={driver}
          stars={stars}
          tags={tags}
          comment={comment}
          commentOpen={commentOpen}
          onStars={setStars}
          onTags={setTags}
          onComment={setComment}
          onOpenComment={() => setCommentOpen(true)}
        />
      </div>
    </ResultPage>
  )
}

/** Figma 24:633 «Поездка отменена». */
export function CancelledScreen({ ride, onReorder }: { ride: RideDetails; onReorder: () => void }) {
  const from = usePlaceTitle(ride.pickup)
  const to = usePlaceTitle(ride.dropoff)
  const refunded = ride.payment_status === 'refunded'
  const method = ride.payment_method === 'kaspi_link' ? 'Kaspi' : 'Наличные'
  const routeText = from && to ? `${from} → ${to}` : '…'
  return (
    <ResultPage
      top="pt-[49px] pb-[34px]"
      footer={
        <Button className="w-full" onClick={onReorder}>
          Заказать снова
        </Button>
      }
    >
      <div className="flex w-full flex-col items-center gap-5">
        <StatusHeading
          icon={X}
          gap="gap-5"
          title="Поездка отменена"
          text={ride.cancel_reason ? `Причина: ${ride.cancel_reason}` : 'Вы отменили заказ до начала поездки'}
        />
        <section className="flex w-full flex-col gap-3 rounded-lg bg-bg-canvas p-5">
          <Receipt
            label={refunded ? 'Возврат' : 'Списано'}
            amount={refunded ? ride.amount_kzt : 0}
            pill={refunded ? { tone: 'info', text: 'Возвращено' } : { tone: 'neutral', text: 'Не списано' }}
            rows={[
              ['Способ', method],
              ['Маршрут', routeText],
            ]}
          />
        </section>
      </div>
    </ResultPage>
  )
}

import type { Offer } from '@/api'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useCountdown } from '@/hooks/use-countdown'
import { useAcceptOffer, useRejectOffer } from '@/hooks/use-driver'
import { formatDistance, formatDuration, formatMoney } from '@/lib/format'

/** A 30-second offer; the countdown follows the server `expires_at`. */
export function OfferCard({ offer }: { offer: Offer }) {
  const secondsLeft = useCountdown(offer.expires_at)
  const accept = useAcceptOffer()
  const reject = useRejectOffer()
  const busy = accept.isPending || reject.isPending
  const expired = secondsLeft === 0

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Новый заказ</span>
          <span className="tabular-nums text-muted-foreground" aria-live="polite">{secondsLeft} с</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3">
        <p className="text-2xl font-semibold">{formatMoney(offer.amount_kzt)}</p>
        <p className="text-sm text-muted-foreground">
          {formatDistance(offer.distance_m)} · {formatDuration(offer.duration_s)}
        </p>
        <ErrorAlert error={accept.error ?? reject.error} />
        <div className="grid grid-cols-2 gap-2">
          <Button variant="outline" disabled={busy || expired} onClick={() => reject.mutate(offer.id)}>
            Отказаться
          </Button>
          <Button disabled={busy || expired} onClick={() => accept.mutate(offer.id)}>
            Принять
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

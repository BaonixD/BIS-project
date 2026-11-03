import { useState } from 'react'
import { ExternalLink } from 'lucide-react'
import { isApiError, type PaymentMethod } from '@/api'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { usePayment, usePayRide, useSetPaymentMethod } from '@/hooks/use-payment'
import { formatDateTime, formatMoney } from '@/lib/format'
import { PAYMENT_STATUS_LABELS } from '@/lib/labels'

/** Study payment (ADR 0009): pressing «Оплатил» marks the ride paid; nothing verifies the money. */
export function PaymentPanel({ rideId }: { rideId: string }) {
  const payment = usePayment(rideId)
  const setMethod = useSetPaymentMethod(rideId)
  const pay = usePayRide(rideId)
  const [kaspiUnavailable, setKaspiUnavailable] = useState(false)

  if (payment.isPending) return <Skeleton className="h-32" />
  if (payment.isError) return <ErrorAlert error={payment.error} />

  const { amount_kzt, method, status, payment_url, paid_at } = payment.data
  const paid = status === 'paid'

  const choose = (next: PaymentMethod) =>
    setMethod.mutate(next, {
      onError: (error) => {
        if (isApiError(error, 'kaspi_unavailable')) setKaspiUnavailable(true)
      },
    })

  return (
    <div className="grid gap-3 rounded-lg border p-3">
      <div className="flex items-center justify-between">
        <p className="text-xl font-semibold">{formatMoney(amount_kzt)}</p>
        <Badge variant={paid ? 'default' : 'secondary'}>{PAYMENT_STATUS_LABELS[status]}</Badge>
      </div>
      {!paid && (
        <Tabs value={method} onValueChange={(value) => choose(value as PaymentMethod)}>
          <TabsList className="w-full">
            <TabsTrigger value="cash" disabled={setMethod.isPending}>Наличные</TabsTrigger>
            {!kaspiUnavailable && (
              <TabsTrigger value="kaspi_link" disabled={setMethod.isPending}>Kaspi</TabsTrigger>
            )}
          </TabsList>
        </Tabs>
      )}
      {method === 'kaspi_link' && payment_url && (
        <Button variant="outline" asChild>
          <a href={payment_url} target="_blank" rel="noopener noreferrer">
            Открыть Kaspi <ExternalLink />
          </a>
        </Button>
      )}
      {method === 'kaspi_link' && !paid && (
        <p className="text-xs text-muted-foreground">Введите сумму {formatMoney(amount_kzt)} в Kaspi вручную.</p>
      )}
      {method === 'cash' && !paid && (
        <p className="text-xs text-muted-foreground">Передайте водителю {formatMoney(amount_kzt)}.</p>
      )}
      <ErrorAlert error={setMethod.error ?? pay.error} />
      {paid ? (
        <p className="text-sm text-muted-foreground">Оплачено {formatDateTime(paid_at)}</p>
      ) : (
        <Button disabled={pay.isPending} onClick={() => pay.mutate()}>Оплатил</Button>
      )}
    </div>
  )
}

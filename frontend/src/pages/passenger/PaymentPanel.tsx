import { ExternalLink } from 'lucide-react'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Button, Skeleton, StatusPill, type StatusTone } from '@/components/ui-kit'
import { usePayment } from '@/hooks/use-payment'
import { formatDateTime, formatMoney } from '@/lib/format'
import { PAYMENT_METHOD_LABELS, PAYMENT_STATUS_LABELS } from '@/lib/labels'
import type { PaymentStatus } from '@/api'

const STATUS_TONE: Record<PaymentStatus, StatusTone> = { unpaid: 'warning', paid: 'success', refunded: 'info' }

/** Study payment (ADR 0009): Kaspi counts as paid when ordered; cash is confirmed by the driver. */
export function PaymentPanel({ rideId }: { rideId: string }) {
  const payment = usePayment(rideId)

  if (payment.isPending) return <Skeleton className="h-32 rounded-lg" />
  if (payment.isError) return <ErrorAlert error={payment.error} />

  const { amount_kzt, method, status, payment_url, paid_at } = payment.data

  return (
    <div className="grid gap-3 rounded-lg bg-bg-subtle p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-callout text-text-secondary">{PAYMENT_METHOD_LABELS[method]}</p>
          <p className="text-display">{formatMoney(amount_kzt)}</p>
        </div>
        <StatusPill tone={STATUS_TONE[status]}>{PAYMENT_STATUS_LABELS[status]}</StatusPill>
      </div>
      {method === 'kaspi_link' && payment_url && (
        <Button variant="secondary" size="md" asChild>
          <a href={payment_url} target="_blank" rel="noopener noreferrer">
            Открыть Kaspi <ExternalLink />
          </a>
        </Button>
      )}
      {method === 'cash' && status === 'unpaid' && (
        <p className="text-caption text-text-secondary">Передайте водителю {formatMoney(amount_kzt)}.</p>
      )}
      {paid_at && <p className="text-caption text-text-secondary">Оплачено {formatDateTime(paid_at)}</p>}
    </div>
  )
}

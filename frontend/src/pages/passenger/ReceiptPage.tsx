import { Printer, Receipt, Share2 } from 'lucide-react'
import { useNavigate, useParams } from 'react-router'
import type { DriverCard, RideDetails } from '@/api'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { FullScreen, ScreenHeader } from '@/components/passenger/layout'
import { StatusHeading } from '@/components/passenger/ride-parts'
import { Button, Skeleton, showToast } from '@/components/ui-kit'
import { usePassengerRide } from '@/hooks/use-rides'
import { t, useLocale } from '@/i18n/core'
import { formatPrice } from './model/format'
import { receiptText } from './model/receipt'
import { useRememberedDriver } from './ride/driver-cache'
import { ReceiptSlip } from './ride/ReceiptSlip'
import { useReceiptLines } from './ride/use-receipt-lines'

async function share(text: string) {
  try {
    if (navigator.share) {
      await navigator.share({ title: t('Чек об оплате'), text })
      return
    }
    await navigator.clipboard.writeText(text)
    showToast({ title: t('Чек скопирован') })
  } catch {
    /* The person closed the share sheet. */
  }
}

function ReceiptActions({ ride, driver }: { ride: RideDetails; driver: DriverCard | null }) {
  useLocale()
  const { lines, paid } = useReceiptLines(ride, driver, true)
  const text = receiptText([...lines, [t('Оплачено'), formatPrice(paid)]])
  return (
    <div className="receipt-actions flex w-full gap-3">
      <Button variant="secondary" className="flex-1" onClick={() => void share(text)}>
        <Share2 className="size-4" aria-hidden />
        {t('Поделиться')}
      </Button>
      <Button variant="secondary" className="flex-1" onClick={() => window.print()}>
        <Printer className="size-4" aria-hidden />
        {t('Сохранить PDF')}
      </Button>
    </div>
  )
}

/** The receipt of a paid ride: opens right after the Kaspi charge and from the history. */
export function ReceiptPage() {
  useLocale()
  const { rideId = '' } = useParams()
  const navigate = useNavigate()
  const query = usePassengerRide(rideId)
  const ride = query.data
  const driver = useRememberedDriver(rideId, ride?.driver)
  const issued = ride && ride.payment_status && ride.payment_status !== 'unpaid'
  return (
    <FullScreen className="bg-bg-subtle">
      <div className="mx-auto flex w-full max-w-[420px] flex-col gap-5 px-4 pt-[calc(56px+env(safe-area-inset-top))] pb-8 lg:pt-8">
        <ScreenHeader title={t('Чек')} back={{ onClick: () => navigate(-1) }} />
        {query.isPending && <Skeleton className="h-96 w-full rounded-lg" />}
        <ErrorAlert error={query.error} />
        {ride && issued && (
          <>
            <ReceiptSlip ride={ride} driver={driver} full />
            <ReceiptActions ride={ride} driver={driver} />
          </>
        )}
        {ride && !issued && (
          <StatusHeading
            icon={Receipt}
            title={t('Чека пока нет')}
            text={t('Чек появится, как только поездка будет оплачена.')}
          />
        )}
      </div>
    </FullScreen>
  )
}

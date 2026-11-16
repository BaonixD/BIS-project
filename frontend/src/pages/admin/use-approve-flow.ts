import { request } from '@/api/request'
import type { DocumentsSummary } from '@/hooks/use-documents'
import { t } from '@/i18n/core'
import { useRef, useState } from 'react'
import { errorMessage, missingFields } from '@/api'
import type { NextAdminDriver, Tariff } from '@/api/driver-types'
import { showToast } from '@/components/ui-kit'
import { useApproveDriver, useSetCarClass } from '@/hooks/use-admin'
import { DRIVER_FIELD_LABELS } from '@/lib/labels'
function fail(error: Error) {
  const fields = missingFields(error).map((field) => DRIVER_FIELD_LABELS()[field] ?? field)
  showToast({
    title: errorMessage(error),
    description: fields.length ? t('Не заполнено: {p0}', { p0: fields.join(', ') }) : undefined,
  })
}
/** «Одобрить» opens the car-class sheet; confirming approves (pending) or changes the class (approved). */
export function useApproveFlow() {
  const approve = useApproveDriver()
  const setCarClass = useSetCarClass()
  const [target, setTarget] = useState<NextAdminDriver | null>(null)
  const review = useRef<{ package_id: string; version: number } | undefined>(undefined)
  const opening = useRef('')
  const open = async (driver: NextAdminDriver) => {
    opening.current = driver.id
    review.current = undefined
    if (driver.approval_status !== 'approved') {
      try {
        const data = await request<DocumentsSummary>(`/admin/drivers/${driver.id}/documents`)
        if (opening.current !== driver.id) return
        if (data.package?.status === 'pending') review.current = { package_id: data.package.id, version: data.package.version }
        else if (!data.legacy_exempt) { showToast({ title: t('Сначала проверьте отправленный пакет документов') }); return }
      } catch (error) { fail(error as Error); return }
    }
    setTarget(driver)
  }
  const confirm = (carClass: Tariff) => {
    if (!target) return
    const close = () => setTarget(null)
    if (target.approval_status === 'approved') {
      setCarClass.mutate({ driverId: target.id, carClass }, { onSuccess: close, onError: fail })
    } else {
      approve.mutate({ driverId: target.id, carClass, review: review.current }, { onSuccess: close, onError: fail })
    }
  }
  return {
    target,
    open,
    close: () => setTarget(null),
    confirm,
    busy: approve.isPending || setCarClass.isPending,
  }
}

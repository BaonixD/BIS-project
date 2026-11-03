import { useState } from 'react'
import { errorMessage, missingFields } from '@/api'
import type { NextAdminDriver, Tariff } from '@/api/driver-types'
import { showToast } from '@/components/ui-kit'
import { useApproveDriver, useSetCarClass } from '@/hooks/use-admin'
import { DRIVER_FIELD_LABELS } from '@/lib/labels'

function fail(error: Error) {
  const fields = missingFields(error).map((field) => DRIVER_FIELD_LABELS[field] ?? field)
  showToast({ title: errorMessage(error), description: fields.length ? `Не заполнено: ${fields.join(', ')}` : undefined })
}

/** «Одобрить» opens the car-class sheet; confirming approves (pending) or changes the class (approved). */
export function useApproveFlow() {
  const approve = useApproveDriver()
  const setCarClass = useSetCarClass()
  const [target, setTarget] = useState<NextAdminDriver | null>(null)

  const confirm = (carClass: Tariff) => {
    if (!target) return
    const close = () => setTarget(null)
    if (target.approval_status === 'approved') {
      setCarClass.mutate({ driverId: target.id, carClass }, { onSuccess: close, onError: fail })
    } else {
      approve.mutate({ driverId: target.id, carClass }, { onSuccess: close, onError: fail })
    }
  }

  return {
    target,
    open: setTarget,
    close: () => setTarget(null),
    confirm,
    busy: approve.isPending || setCarClass.isPending,
  }
}

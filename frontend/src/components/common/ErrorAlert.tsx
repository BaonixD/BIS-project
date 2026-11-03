import { CircleAlert } from 'lucide-react'
import { ApiError, errorMessage, missingFields } from '@/api'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { DRIVER_FIELD_LABELS } from '@/lib/labels'

export function ErrorAlert({ error, title }: { error: unknown; title?: string }) {
  if (!error) return null
  const fields = missingFields(error)
  const requestId = error instanceof ApiError ? error.requestId : null
  return (
    <Alert variant="destructive">
      <CircleAlert />
      <AlertTitle>{title ?? errorMessage(error)}</AlertTitle>
      {(title || fields.length > 0 || requestId) && (
        <AlertDescription>
          {title && <p>{errorMessage(error)}</p>}
          {fields.length > 0 && (
            <p>Не заполнено: {fields.map((f) => DRIVER_FIELD_LABELS[f] ?? f).join(', ')}</p>
          )}
          {requestId && <p className="text-xs opacity-70">request_id: {requestId}</p>}
        </AlertDescription>
      )}
    </Alert>
  )
}

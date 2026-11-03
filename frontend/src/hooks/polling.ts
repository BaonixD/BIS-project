import { isApiError } from '@/api'

export const RIDE_POLL_MS = 3_000
export const OFFERS_POLL_MS = 3_000
export const LOCATION_REPORT_MS = 10_000
export const DRIVER_PENDING_POLL_MS = 20_000

export function retryUnlessClientError(failureCount: number, error: Error): boolean {
  if (isApiError(error) && error.status >= 400 && error.status < 500) return false
  return failureCount < 2
}

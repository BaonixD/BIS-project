import { RideHistoryPage } from '@/pages/shared/RideHistoryPage'

export function HistoryPage() {
  return <RideHistoryPage linkTo={(ride) => `/ride/${ride.id}`} />
}

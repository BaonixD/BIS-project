import type { PageParams, RideStatus, UserRole } from '@/api'

export interface RideHistoryFilters extends PageParams {
  status?: RideStatus[]
  created_from?: string
  created_to?: string
}

export interface AdminRideFilters extends RideHistoryFilters {
  passenger_id?: string
  driver_id?: string
}

export const queryKeys = {
  session: ['session'] as const,
  me: ['users', 'me'] as const,
  rides: {
    all: ['rides'] as const,
    history: (filters: RideHistoryFilters) => ['rides', 'history', filters] as const,
    active: (statuses: readonly RideStatus[]) => ['rides', 'active', statuses] as const,
    detail: (rideId: string) => ['rides', 'detail', rideId] as const,
    payment: (rideId: string) => ['rides', 'payment', rideId] as const,
  },
  driver: {
    me: ['drivers', 'me'] as const,
    offers: ['drivers', 'me', 'offers'] as const,
  },
  admin: {
    drivers: (approvalStatus: string | undefined, page: PageParams) =>
      ['admin', 'drivers', approvalStatus, page] as const,
    rides: (filters: AdminRideFilters) => ['admin', 'rides', filters] as const,
    users: (role: UserRole | undefined, page: PageParams) => ['admin', 'users', role, page] as const,
  },
}

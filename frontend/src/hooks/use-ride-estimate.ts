import { useQuery } from '@tanstack/react-query'
import { api, unwrap, type RideDetails, type RideEstimateData } from '@/api'

export function useRideEstimate(ride: RideDetails) {
  const active = ride.status === 'assigned' || ride.status === 'in_progress'
  return useQuery({
    queryKey: ['rides', 'estimate', ride.id, ride.driver_id, ride.status],
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/rides/{ride_id}/estimate', {
          params: { path: { ride_id: ride.id } },
        }),
      ),
    enabled: active,
    staleTime: 30_000,
    refetchInterval: active ? 60_000 : false,
    refetchIntervalInBackground: false,
    retry: false,
  })
}

export function estimateIsFresh(data: RideEstimateData, now: number): boolean {
  const age = now - Date.parse(data.generated_at)
  return !data.stale && data.source !== 'unavailable' && age >= -5_000 && age < 90_000
}

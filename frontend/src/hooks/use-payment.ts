import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '@/api'
import { queryKeys } from './query-keys'

export function usePayment(rideId: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.rides.payment(rideId),
    queryFn: () =>
      unwrap(api.GET('/api/v1/rides/{ride_id}/payment', { params: { path: { ride_id: rideId } } })),
    enabled: options.enabled ?? true,
  })
}

/** Driver confirms the cash after a completed cash ride; Kaspi rides are paid when ordered. */
export function useConfirmCashReceived(rideId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () =>
      unwrap(
        api.POST('/api/v1/rides/{ride_id}/payment/cash-received', {
          params: { path: { ride_id: rideId } },
        }),
      ),
    onSuccess: (payment) => {
      queryClient.setQueryData(queryKeys.rides.payment(rideId), payment)
      return queryClient.invalidateQueries({ queryKey: ['rides', 'history'] })
    },
  })
}

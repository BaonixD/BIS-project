import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Payment, type PaymentMethod } from '@/api'
import { queryKeys } from './query-keys'

export function usePayment(rideId: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.rides.payment(rideId),
    queryFn: () =>
      unwrap(api.GET('/api/v1/rides/{ride_id}/payment', { params: { path: { ride_id: rideId } } })),
    enabled: options.enabled ?? true,
  })
}

function useStorePayment(rideId: string) {
  const queryClient = useQueryClient()
  return (payment: Payment) => {
    queryClient.setQueryData(queryKeys.rides.payment(rideId), payment)
    return queryClient.invalidateQueries({ queryKey: ['rides', 'history'] })
  }
}

export function useSetPaymentMethod(rideId: string) {
  const store = useStorePayment(rideId)
  return useMutation({
    mutationFn: (method: PaymentMethod) =>
      unwrap(
        api.PUT('/api/v1/rides/{ride_id}/payment/method', {
          params: { path: { ride_id: rideId } },
          body: { method },
        }),
      ),
    onSuccess: store,
  })
}

export function usePayRide(rideId: string) {
  const store = useStorePayment(rideId)
  return useMutation({
    mutationFn: () =>
      unwrap(
        api.POST('/api/v1/rides/{ride_id}/payment/pay', { params: { path: { ride_id: rideId } } }),
      ),
    onSuccess: store,
  })
}

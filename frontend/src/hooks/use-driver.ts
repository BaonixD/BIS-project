import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Coordinates, type Driver, type DriverProfileUpdate } from '@/api'
import { DRIVER_PENDING_POLL_MS, OFFERS_POLL_MS } from './polling'
import { queryKeys } from './query-keys'

export function useDriverProfile() {
  return useQuery({
    queryKey: queryKeys.driver.me,
    queryFn: () => unwrap(api.GET('/api/v1/drivers/me')),
    refetchInterval: (query) =>
      query.state.data?.approval_status === 'pending' ? DRIVER_PENDING_POLL_MS : false,
  })
}

function useStoreDriver() {
  const queryClient = useQueryClient()
  return (driver: Driver) => queryClient.setQueryData(queryKeys.driver.me, driver)
}

export function useUpdateDriverProfile() {
  const store = useStoreDriver()
  return useMutation({
    mutationFn: (body: DriverProfileUpdate) => unwrap(api.PATCH('/api/v1/drivers/me', { body })),
    onSuccess: store,
  })
}

export function useSetAvailability() {
  const store = useStoreDriver()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (online: boolean) =>
      unwrap(api.PUT('/api/v1/drivers/me/availability', { body: { online } })),
    onSuccess: (driver) => {
      store(driver)
      return queryClient.invalidateQueries({ queryKey: queryKeys.driver.offers })
    },
  })
}

export function useSendLocation() {
  const store = useStoreDriver()
  return useMutation({
    mutationFn: (point: Coordinates) =>
      unwrap(api.PUT('/api/v1/drivers/me/location', { body: point })),
    onSuccess: store,
  })
}

export function useDriverOffers(options: { enabled: boolean }) {
  return useQuery({
    queryKey: queryKeys.driver.offers,
    queryFn: () => unwrap(api.GET('/api/v1/drivers/me/offers')),
    enabled: options.enabled,
    refetchInterval: options.enabled ? OFFERS_POLL_MS : false,
  })
}

function useInvalidateOffers() {
  const queryClient = useQueryClient()
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.driver.offers }),
      queryClient.invalidateQueries({ queryKey: ['rides', 'active'] }),
    ])
}

export function useAcceptOffer() {
  const invalidate = useInvalidateOffers()
  return useMutation({
    mutationFn: (offerId: string) =>
      unwrap(
        api.POST('/api/v1/ride-offers/{offer_id}/accept', {
          params: { path: { offer_id: offerId } },
        }),
      ),
    onSettled: invalidate,
  })
}

export function useRejectOffer() {
  const invalidate = useInvalidateOffers()
  return useMutation({
    mutationFn: (offerId: string) =>
      unwrap(
        api.POST('/api/v1/ride-offers/{offer_id}/reject', {
          params: { path: { offer_id: offerId } },
        }),
      ),
    onSettled: invalidate,
  })
}

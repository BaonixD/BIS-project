import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  api,
  isApiError,
  isRideActive,
  NETWORK_ERROR_CODE,
  unwrap,
  type Coordinates,
  type RideStatus,
} from '@/api'
import { RIDE_POLL_MS } from './polling'
import { queryKeys, type RideHistoryFilters } from './query-keys'

export interface RoutePoints {
  pickup: Coordinates
  dropoff: Coordinates
}

export function useQuote() {
  return useMutation({
    mutationFn: ({ pickup, dropoff }: RoutePoints) =>
      unwrap(api.POST('/api/v1/rides/quotes', { body: { pickup, dropoff } })),
  })
}

export function useRoutePreview() {
  return useMutation({
    mutationFn: ({ pickup, dropoff }: RoutePoints) =>
      unwrap(api.POST('/api/v1/geo/route', { body: { origin: pickup, destination: dropoff } })),
  })
}

export interface CreateRideVariables {
  quoteId: string
  idempotencyKey: string
}

export function newIdempotencyKey(): string {
  return crypto.randomUUID()
}

/** Pass a fresh key per «Заказать» press; react-query retries reuse it on network failures. */
export function useCreateRide() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ quoteId, idempotencyKey }: CreateRideVariables) =>
      unwrap(
        api.POST('/api/v1/rides', {
          params: { header: { 'Idempotency-Key': idempotencyKey } },
          body: { quote_id: quoteId },
        }),
      ),
    retry: (failureCount, error) => isApiError(error, NETWORK_ERROR_CODE) && failureCount < 2,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.rides.all }),
  })
}

export function useRide(rideId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.rides.detail(rideId ?? ''),
    queryFn: () =>
      unwrap(api.GET('/api/v1/rides/{ride_id}', { params: { path: { ride_id: rideId ?? '' } } })),
    enabled: Boolean(rideId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (query.state.error) return false
      return status && isRideActive(status) ? RIDE_POLL_MS : false
    },
  })
}

export function useActiveRide(statuses: readonly RideStatus[], options: { pollMs?: number } = {}) {
  return useQuery({
    queryKey: queryKeys.rides.active(statuses),
    queryFn: async () => {
      const page = await unwrap(
        api.GET('/api/v1/rides', { params: { query: { status: [...statuses], limit: 1 } } }),
      )
      return page.items[0] ?? null
    },
    refetchInterval: options.pollMs ?? false,
  })
}

export function useRideHistory(filters: RideHistoryFilters) {
  return useQuery({
    queryKey: queryKeys.rides.history(filters),
    queryFn: () => unwrap(api.GET('/api/v1/rides', { params: { query: filters } })),
    placeholderData: keepPreviousData,
  })
}

export type DriverRideCommand = 'arrive' | 'start' | 'complete'

function postDriverCommand(rideId: string, command: DriverRideCommand) {
  const params = { params: { path: { ride_id: rideId } } }
  switch (command) {
    case 'arrive':
      return unwrap(api.POST('/api/v1/rides/{ride_id}/arrive', params))
    case 'start':
      return unwrap(api.POST('/api/v1/rides/{ride_id}/start', params))
    case 'complete':
      return unwrap(api.POST('/api/v1/rides/{ride_id}/complete', params))
  }
}

function useInvalidateRide(rideId: string) {
  const queryClient = useQueryClient()
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.rides.detail(rideId) }),
      queryClient.invalidateQueries({ queryKey: ['rides', 'active'] }),
      queryClient.invalidateQueries({ queryKey: ['rides', 'history'] }),
    ])
}

export function useDriverRideCommand(rideId: string) {
  const invalidate = useInvalidateRide(rideId)
  return useMutation({
    mutationFn: (command: DriverRideCommand) => postDriverCommand(rideId, command),
    onSettled: invalidate,
  })
}

export function useCancelRide(rideId: string) {
  const invalidate = useInvalidateRide(rideId)
  return useMutation({
    mutationFn: (reason?: string) =>
      unwrap(
        api.POST('/api/v1/rides/{ride_id}/cancel', {
          params: { path: { ride_id: rideId } },
          body: reason ? { reason } : null,
        }),
      ),
    onSettled: invalidate,
  })
}

export function useReleaseRide(rideId: string) {
  const invalidate = useInvalidateRide(rideId)
  return useMutation({
    mutationFn: (reason: string) =>
      unwrap(
        api.POST('/api/v1/rides/{ride_id}/release', {
          params: { path: { ride_id: rideId } },
          body: { reason },
        }),
      ),
    onSettled: invalidate,
  })
}

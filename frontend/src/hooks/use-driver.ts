import type { Tariff } from '@/api/driver-types'
import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Coordinates, type DriverProfileUpdate, type Page } from '@/api'
import type { NextDriver, NextOffer } from '@/api/driver-types'
import { DRIVER_PENDING_POLL_MS, OFFERS_POLL_MS } from './polling'
import { queryKeys } from './query-keys'

export function useDriverProfile() {
  return useQuery({
    queryKey: queryKeys.driver.me,
    queryFn: async () => (await unwrap(api.GET('/api/v1/drivers/me'))) as NextDriver,
    refetchInterval: (query) =>
      query.state.data?.approval_status === 'pending' ? DRIVER_PENDING_POLL_MS : false,
  })
}

function useStoreDriver() {
  const queryClient = useQueryClient()
  return (driver: unknown) => queryClient.setQueryData(queryKeys.driver.me, driver as NextDriver)
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
    mutationFn: (selection: boolean | { online: boolean; categories: Tariff[] }) =>
      unwrap(
        api.PUT('/api/v1/drivers/me/availability', {
          body: typeof selection === 'boolean' ? { online: selection } : selection,
        }),
      ),
    onSuccess: (driver) => {
      store(driver)
      rememberOnline(driver.online)
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
    queryFn: async () => (await unwrap(api.GET('/api/v1/drivers/me/offers'))) as Page<NextOffer>,
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

const ONLINE_SINCE_KEY = 'bis.driver.onlineSince'

function readOnlineSince(): number | null {
  const stored = Number(localStorage.getItem(ONLINE_SINCE_KEY))
  return Number.isFinite(stored) && stored > 0 ? stored : null
}

/** Remembers when the driver went online (the API does not report it); called on availability changes. */
function rememberOnline(online: boolean) {
  if (!online) localStorage.removeItem(ONLINE_SINCE_KEY)
  else if (readOnlineSince() === null) localStorage.setItem(ONLINE_SINCE_KEY, String(Date.now()))
}

/** When the current shift started: stored on «ВЫЙТИ», or this page's first render after a reload. */
export function useOnlineSince(online: boolean): number | null {
  const [mountedAt] = useState(() => Date.now())
  return online ? (readOnlineSince() ?? mountedAt) : null
}

const TRACKED_RIDE_KEY = 'bis.driver.rideId'

/** The ride whose screens the driver still sees (active, or finished but not dismissed); kept across reloads. */
export function useTrackedRideId(activeRideId: string | null | undefined) {
  const [rideId, setRideId] = useState<string | null>(() => localStorage.getItem(TRACKED_RIDE_KEY))
  const [seenActive, setSeenActive] = useState(activeRideId)
  if (activeRideId !== seenActive) {
    setSeenActive(activeRideId)
    if (activeRideId) setRideId(activeRideId)
  }

  useEffect(() => {
    if (rideId) localStorage.setItem(TRACKED_RIDE_KEY, rideId)
    else localStorage.removeItem(TRACKED_RIDE_KEY)
  }, [rideId])

  return [rideId, setRideId] as const
}

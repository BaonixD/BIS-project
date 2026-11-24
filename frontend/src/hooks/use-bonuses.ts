import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '@/api'
import type { Tariff } from '@/api/passenger-types'
import { queryKeys } from './query-keys'

const BONUS_KEY = ['bonuses', 'me'] as const
const upgradesKey = (rideId: string) => ['rides', 'upgrades', rideId] as const

/** The passenger's bonus balance; 1 bonus = 1 ₸. */
export function useBonusBalance(enabled = true) {
  return useQuery({
    queryKey: BONUS_KEY,
    queryFn: () => unwrap(api.GET('/api/v1/bonuses/me')),
    enabled,
    staleTime: 30_000,
  })
}

/** Higher tariffs of a searching ride with their surcharge; empty once a driver accepted. */
export function useRideUpgrades(rideId: string, enabled: boolean) {
  return useQuery({
    queryKey: upgradesKey(rideId),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/rides/{ride_id}/upgrades', { params: { path: { ride_id: rideId } } }),
      ),
    enabled,
    refetchInterval: enabled ? 10_000 : false,
  })
}

export function useUpgradeRide(rideId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ tariff, useBonus }: { tariff: Tariff; useBonus: boolean }) =>
      unwrap(
        api.POST('/api/v1/rides/{ride_id}/upgrade', {
          params: { path: { ride_id: rideId } },
          body: { tariff, use_bonus: useBonus },
        }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.rides.all })
      void client.invalidateQueries({ queryKey: BONUS_KEY })
    },
  })
}

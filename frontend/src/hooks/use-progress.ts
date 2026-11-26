import { useQuery } from '@tanstack/react-query'
import { api, unwrap } from '@/api'

export const PROGRESS_KEY = ['achievements'] as const

/** Level, XP, streak, the weekly quest and achievements of the signed-in user. */
export function useProgress({ fresh = false }: { fresh?: boolean } = {}) {
  return useQuery({
    queryKey: PROGRESS_KEY,
    queryFn: () => unwrap(api.GET('/api/v1/users/me/achievements')),
    refetchOnMount: fresh ? 'always' : true,
  })
}

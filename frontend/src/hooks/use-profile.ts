import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type MyProfileUpdate } from '@/api'
import { queryKeys } from './query-keys'

export function useMyProfile(enabled = true) {
  return useQuery({
    enabled,
    queryKey: queryKeys.me,
    queryFn: () => unwrap(api.GET('/api/v1/users/me')),
  })
}

export function useUpdateMyProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: MyProfileUpdate) => unwrap(api.PATCH('/api/v1/users/me', { body })),
    onSuccess: (profile) => queryClient.setQueryData(queryKeys.me, profile),
  })
}

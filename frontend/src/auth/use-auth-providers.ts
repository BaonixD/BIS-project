import { useQuery } from '@tanstack/react-query'
import { fetchAuthProviders } from './session-api'

/** Sign-in methods the server offers; `google_client_id` is null when Google sign-in is off. */
export function useAuthProviders() {
  return useQuery({
    queryKey: ['auth', 'providers'],
    queryFn: fetchAuthProviders,
    staleTime: Infinity,
    retry: false,
  })
}

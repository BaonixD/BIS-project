import { QueryClient } from '@tanstack/react-query'
import { retryUnlessClientError } from '@/hooks/polling'

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: retryUnlessClientError, staleTime: 5_000 },
      mutations: { retry: false },
    },
  })
}

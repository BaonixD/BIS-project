import { useEffect, useMemo, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { onUnauthenticated, type Session } from '@/api'
import { queryKeys } from '@/hooks/query-keys'
import { fetchSession, login, loginWithGoogle, logout, register } from './session-api'
import { SessionContext, type SessionContextValue } from './session-context'

function resetUserData(queryClient: QueryClient, session: Session | null): void {
  queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== queryKeys.session[0] })
  queryClient.setQueryData(queryKeys.session, session)
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const session = useQuery({
    queryKey: queryKeys.session,
    queryFn: fetchSession,
    staleTime: Infinity,
    retry: false,
  })

  useEffect(
    () => onUnauthenticated(() => resetUserData(queryClient, null)),
    [queryClient],
  )

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: (data) => resetUserData(queryClient, data),
  })
  const googleLoginMutation = useMutation({
    mutationFn: loginWithGoogle,
    onSuccess: (data) => resetUserData(queryClient, data),
  })
  const registerMutation = useMutation({ mutationFn: register })
  const logoutMutation = useMutation({
    mutationFn: logout,
    onSettled: () => resetUserData(queryClient, null),
  })

  const user = session.data?.user ?? null
  const status = session.isPending ? 'loading' : user ? 'authenticated' : 'anonymous'

  const value = useMemo<SessionContextValue>(
    () => ({
      status,
      user,
      login: loginMutation,
      register: registerMutation,
      logout: logoutMutation,
      googleLogin: googleLoginMutation,
    }),
    [status, user, loginMutation, registerMutation, logoutMutation, googleLoginMutation],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

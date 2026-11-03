import { createContext } from 'react'
import type { UseMutationResult } from '@tanstack/react-query'
import type { LoginRequest, RegisterRequest, Session, User } from '@/api'

export type SessionStatus = 'loading' | 'authenticated' | 'anonymous'

export interface SessionContextValue {
  status: SessionStatus
  user: User | null
  login: UseMutationResult<Session, Error, LoginRequest>
  register: UseMutationResult<User, Error, RegisterRequest>
  logout: UseMutationResult<void, Error, void>
}

export const SessionContext = createContext<SessionContextValue | null>(null)

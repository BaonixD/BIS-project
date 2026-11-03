import { api, isApiError, setCsrfToken, unwrap } from '@/api'
import type { LoginRequest, RegisterRequest, Session, User } from '@/api'

export async function fetchSession(): Promise<Session | null> {
  try {
    const session = await unwrap(api.GET('/api/v1/auth/session'))
    setCsrfToken(session.csrf_token)
    return session
  } catch (error) {
    if (isApiError(error) && error.status === 401) {
      setCsrfToken(null)
      return null
    }
    throw error
  }
}

export async function login(body: LoginRequest): Promise<Session> {
  const session = await unwrap(api.POST('/api/v1/auth/login', { body }))
  setCsrfToken(session.csrf_token)
  return session
}

export function register(body: RegisterRequest): Promise<User> {
  return unwrap(api.POST('/api/v1/auth/register', { body }))
}

export async function logout(): Promise<void> {
  try {
    await unwrap(api.POST('/api/v1/auth/logout'))
  } finally {
    setCsrfToken(null)
  }
}

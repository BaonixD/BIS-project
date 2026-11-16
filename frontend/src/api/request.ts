import { getCsrfToken } from './csrf'
import { networkError, toApiError } from './errors'
import { fetchSession } from '@/auth/session-api'

/** Multipart and new JSON endpoints share session, CSRF and error handling. */
export async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.method && !['GET', 'HEAD'].includes(init.method) && getCsrfToken()) headers.set('X-CSRF-Token', getCsrfToken()!)
  let response: Response
  try { response = await fetch(`/api/v1${path}`, { ...init, headers, credentials: 'include' }) } catch (error) { throw networkError(error) }
  const body: unknown = response.status === 204 ? null : await response.json()
  if (response.ok) return body as T
  const error = toApiError(body, response)
  if (error.code === 'csrf_failed' && retry) { await fetchSession(); return request(path, init, false) }
  if (error.status === 401) await fetchSession()
  throw error
}

export const jsonBody = (value: unknown): RequestInit => ({ headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) })

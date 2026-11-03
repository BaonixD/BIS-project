import createClient, { type Middleware } from 'openapi-fetch'
import { getCsrfToken, setCsrfToken } from './csrf'
import { networkError, toApiError } from './errors'
import type { paths } from './schema'

const CSRF_HEADER = 'X-CSRF-Token'
const SESSION_PATH = '/api/v1/auth/session'
const LOGIN_PATH = '/api/v1/auth/login'
const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

type Listener = () => void
const unauthenticatedListeners = new Set<Listener>()

export function onUnauthenticated(listener: Listener): () => void {
  unauthenticatedListeners.add(listener)
  return () => unauthenticatedListeners.delete(listener)
}

async function errorCode(response: Response): Promise<string | null> {
  try {
    const body: unknown = await response.clone().json()
    const error = (body as { error?: { code?: unknown } } | null)?.error
    return typeof error?.code === 'string' ? error.code : null
  } catch {
    return null
  }
}

async function refreshCsrfToken(): Promise<boolean> {
  const response = await fetch(SESSION_PATH, { credentials: 'include' })
  if (!response.ok) return false
  const session = (await response.json()) as { csrf_token: string }
  setCsrfToken(session.csrf_token)
  return true
}

const pendingRetries = new Map<string, Request>()

const sessionMiddleware: Middleware = {
  onRequest({ request, id }) {
    if (!MUTATING_METHODS.has(request.method)) return request
    const token = getCsrfToken()
    if (token) request.headers.set(CSRF_HEADER, token)
    pendingRetries.set(id, request.clone())
    return request
  },

  async onResponse({ response, schemaPath, id }) {
    const retry = pendingRetries.get(id)
    pendingRetries.delete(id)
    if (response.ok) return response
    const code = await errorCode(response)
    if (code === 'csrf_failed' && retry && (await refreshCsrfToken())) {
      retry.headers.set(CSRF_HEADER, getCsrfToken() ?? '')
      return fetch(retry)
    }
    if (code === 'not_authenticated' && schemaPath !== LOGIN_PATH) {
      setCsrfToken(null)
      unauthenticatedListeners.forEach((listener) => listener())
    }
    return response
  },

  onError({ error, id }) {
    pendingRetries.delete(id)
    return networkError(error)
  },
}

export const api = createClient<paths>({ baseUrl: '', credentials: 'include' })
api.use(sessionMiddleware)

interface FetchResult<T> {
  data?: T
  error?: unknown
  response: Response
}

export async function unwrap<T>(request: Promise<FetchResult<T>>): Promise<T> {
  const { data, error, response } = await request
  if (!response.ok) throw toApiError(error, response)
  return data as T
}

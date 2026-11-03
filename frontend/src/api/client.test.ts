import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

type Handler = (request: Request) => Response | Promise<Response>

function json(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
}

function errorBody(code: string, message = code) {
  return { error: { code, message, details: {} }, request_id: 'req-1' }
}

let requests: Request[]

/** Browsers resolve relative request URLs against the page; Node's Request does not. */
class BrowserLikeRequest extends Request {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    super(typeof input === 'string' ? new URL(input, window.location.origin) : input, init)
  }
}

async function load(handler: Handler) {
  requests = []
  vi.stubGlobal('Request', BrowserLikeRequest)
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
      requests.push(request.clone())
      return handler(request)
    }),
  )
  vi.resetModules()
  return import('./index')
}

beforeEach(() => vi.unstubAllGlobals())
afterEach(() => vi.unstubAllGlobals())

describe('API client', () => {
  it('adds the CSRF token to mutating requests only', async () => {
    const api = await load(() => json({ status: 'ok' }))
    api.setCsrfToken('token-1')
    await api.api.GET('/api/v1/users/me')
    await api.api.POST('/api/v1/auth/logout')
    expect(requests[0]?.headers.get('X-CSRF-Token')).toBeNull()
    expect(requests[1]?.headers.get('X-CSRF-Token')).toBe('token-1')
  })

  it('refreshes the CSRF token and retries once after csrf_failed', async () => {
    let attempt = 0
    const api = await load((request) => {
      if (request.url.endsWith('/api/v1/auth/session')) return json({ csrf_token: 'token-2', user: {} })
      attempt += 1
      return attempt === 1 ? json(errorBody('csrf_failed'), 403) : new Response(null, { status: 204 })
    })
    api.setCsrfToken('stale')
    const { response } = await api.api.POST('/api/v1/auth/logout')
    expect(response.status).toBe(204)
    const retried = requests.filter((request) => request.url.endsWith('/api/v1/auth/logout'))
    expect(retried.map((request) => request.headers.get('X-CSRF-Token'))).toEqual(['stale', 'token-2'])
  })

  it('turns an error envelope into an ApiError', async () => {
    const api = await load(() => json(errorBody('invalid_credentials', 'Bad login'), 401))
    const error = await api
      .unwrap(api.api.POST('/api/v1/auth/login', { body: { username: 'a', password: 'b' } }))
      .catch((caught: unknown) => caught)
    expect(api.isApiError(error, 'invalid_credentials')).toBe(true)
    expect(error).toMatchObject({ status: 401, message: 'Bad login', requestId: 'req-1' })
    expect(api.errorMessage(error)).toBe('Неверный логин или пароль.')
  })

  it('reports a non-JSON failure as unknown_error', async () => {
    const api = await load(() => new Response('Bad gateway', { status: 502 }))
    const error = await api.unwrap(api.api.GET('/api/v1/users/me')).catch((caught: unknown) => caught)
    expect(error).toMatchObject({ status: 502, code: 'unknown_error' })
  })

  it('notifies listeners when the session is gone', async () => {
    const api = await load(() => json(errorBody('not_authenticated'), 401))
    const listener = vi.fn()
    api.onUnauthenticated(listener)
    await api.api.GET('/api/v1/users/me')
    expect(listener).toHaveBeenCalledOnce()
  })
})

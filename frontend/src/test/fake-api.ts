import { vi } from 'vitest'

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH'
type Init = { params?: { path?: Record<string, string>; query?: Record<string, unknown> }; body?: unknown }
type Handler = (init: Init) => unknown

export interface FakeCall {
  method: Method
  path: string
  init: Init
}

/** An `api` stand-in for `vi.mock('@/api/client')`: routes by «METHOD path» (the OpenAPI template). */
export function createFakeApi() {
  const routes = new Map<string, Handler>()
  const calls: FakeCall[] = []

  const call = (method: Method) =>
    vi.fn(async (path: string, init: Init = {}) => {
      calls.push({ method, path, init })
      const handler = routes.get(`${method} ${path}`)
      if (!handler) {
        return {
          error: { error: { code: 'not_found', message: path, details: {} } },
          response: new Response(null, { status: 404 }),
        }
      }
      const result = handler(init)
      if (result instanceof Response) return { error: await result.clone().json(), response: result }
      return { data: result, response: new Response(null, { status: 200 }) }
    })

  return {
    api: { GET: call('GET'), POST: call('POST'), PUT: call('PUT'), PATCH: call('PATCH'), use: vi.fn() },
    calls,
    on(route: `${Method} ${string}`, handler: Handler) {
      routes.set(route, handler)
    },
    reset() {
      routes.clear()
      calls.length = 0
    },
  }
}

export function apiError(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: code, details: {} }, request_id: 'req-test' }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** Node 25 ships a global `localStorage` that shadows jsdom's and needs a file; tests use this one. */
export function memoryStorage(): Storage {
  const items = new Map<string, string>()
  return {
    get length() {
      return items.size
    },
    clear: () => items.clear(),
    getItem: (key) => items.get(key) ?? null,
    key: (index) => [...items.keys()][index] ?? null,
    removeItem: (key) => void items.delete(key),
    setItem: (key, value) => void items.set(key, String(value)),
  }
}

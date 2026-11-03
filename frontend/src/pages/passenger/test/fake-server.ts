/**
 * A fetch stub for passenger component tests. Install it with `vi.hoisted(installFakeFetch)`
 * so openapi-fetch captures it when the API client module is created.
 */
export type Handler = (request: Request, body: unknown) => unknown

export interface FakeServer {
  routes: Map<string, Handler>
  calls: { method: string; path: string; body: unknown }[]
}

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

export function installFakeFetch(): FakeServer {
  const server: FakeServer = { routes: new Map(), calls: [] }
  const NativeRequest = globalThis.Request

  class BrowserLikeRequest extends NativeRequest {
    constructor(input: RequestInfo | URL, init?: RequestInit) {
      super(typeof input === 'string' ? new URL(input, 'http://localhost') : input, init)
    }
  }

  globalThis.Request = BrowserLikeRequest as typeof Request
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof NativeRequest ? input : new BrowserLikeRequest(input as string, init)
    const url = new URL(request.url)
    if (url.hostname.includes('nominatim')) return json([])
    const text = await request.clone().text()
    const body: unknown = text ? JSON.parse(text) : null
    server.calls.push({ method: request.method, path: url.pathname, body })
    const handler = server.routes.get(`${request.method} ${url.pathname}`)
    if (!handler) return json({ error: { code: 'not_found', message: 'not mocked', details: {} } }, 404)
    const result = await handler(request, body)
    return result instanceof Response ? result : json(result)
  }
  return server
}

/** jsdom on recent Node lacks a working Web Storage: a Map-backed one for tests. */
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

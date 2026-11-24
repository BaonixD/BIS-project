/* TulparTaxi service worker: fast start and an offline screen; the API is never cached.
 * The build stamps BUILD (vite.config.ts), so every release gets its own caches; the old ones
 * are removed when the new worker takes over after «Обновить». */
const BUILD = '__BUILD_ID__'
const VERSION = `tulpar-${BUILD}`
const SHELL = `${VERSION}-shell`
const ASSETS = `${VERSION}-assets`
const TILES = `${VERSION}-tiles`
const OFFLINE_URL = '/offline.html'
const SHELL_FILES = ['/', OFFLINE_URL, '/manifest.webmanifest', '/icons/icon-192.png', '/favicon.png']
const TILE_HOSTS = ['tiles.openfreemap.org']
const LIMITS = { [TILES]: 300 }

self.addEventListener('install', (event) => {
  event.waitUntil(
    Promise.all([
      caches.open(SHELL).then((cache) => cache.addAll(SHELL_FILES)),
      // Every screen of this build, so a screen never opened before still works offline.
      fetch('/precache.json', { cache: 'no-store' })
        .then((response) => (response.ok ? response.json() : []))
        .then((files) => caches.open(ASSETS).then((cache) => cache.addAll(files)))
        .catch(() => undefined),
    ]),
  )
})

// The page asks for the switch (the «Обновить» button), so a ride is never reloaded by surprise.
self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => !key.startsWith(VERSION)).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (url.origin === self.location.origin) {
    // Orders, payments, statuses and chats must always be fresh and are personal: network only.
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/health')) return
    if (url.pathname === '/sw.js') return
    if (request.mode === 'navigate') return event.respondWith(page(request))
    if (url.pathname.startsWith('/assets/')) return event.respondWith(cacheFirst(request, ASSETS))
    return event.respondWith(staleWhileRevalidate(request, SHELL))
  }
  if (TILE_HOSTS.includes(url.hostname)) event.respondWith(staleWhileRevalidate(request, TILES))
})

/** Fresh HTML when online (and remembered); the last good one, or the offline page, when not. */
async function page(request) {
  const cache = await caches.open(SHELL)
  try {
    const response = await fetch(request)
    if (response.ok) cache.put('/', response.clone())
    return response
  } catch {
    return (await cache.match('/')) || (await cache.match(OFFLINE_URL)) || Response.error()
  }
}

/** Vite's /assets/ files carry a content hash, so a cached copy never goes stale. */
async function cacheFirst(request, name) {
  const cache = await caches.open(name)
  const cached = await cache.match(request)
  if (cached) return cached
  const response = await fetch(request)
  if (response.ok) {
    await cache.put(request, response.clone())
    trim(name)
  }
  return response
}

async function staleWhileRevalidate(request, name) {
  const cache = await caches.open(name)
  const cached = await cache.match(request)
  const network = fetch(request)
    .then((response) => {
      if (response.ok || response.type === 'opaque') {
        cache.put(request, response.clone()).then(() => trim(name))
      }
      return response
    })
    .catch(() => cached)
  return cached || network
}

async function trim(name) {
  const limit = LIMITS[name]
  if (!limit) return
  const cache = await caches.open(name)
  const keys = await cache.keys()
  await Promise.all(keys.slice(0, Math.max(0, keys.length - limit)).map((key) => cache.delete(key)))
}

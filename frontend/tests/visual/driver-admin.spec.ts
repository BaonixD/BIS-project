/// <reference lib="dom" />
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test, type Browser, type Page, type Route } from '@playwright/test'

/**
 * Driver and admin screens against the Figma frames (tests/visual/figma/*.png).
 * The API and Nominatim are mocked, map tiles are blocked (the Figma «Map/Base» art is not a tile).
 * Each frame gets `screenshots/<name>.png` and `screenshots/compare-<name>.png` (Figma | app | diff).
 * Mobile frames include the phone's 47px status bar; the page reserves that space itself,
 * so it is rendered 390×844 and compared with the whole frame.
 */

const OUT = path.join(import.meta.dirname, 'screenshots')
const FIGMA = path.join(import.meta.dirname, 'figma')
mkdirSync(OUT, { recursive: true })

const STATUS_BAR = 0
const NOW = '2026-11-03T09:00:06Z'
const MOBILE = { width: 390, height: 844 }
const DESKTOP = { width: 1440, height: 900 }

const P = {
  abaya: { latitude: 43.2399, longitude: 76.915 },
  esentai: { latitude: 43.2185, longitude: 76.9282 },
  satpaeva: { latitude: 43.2361, longitude: 76.9165 },
  mega: { latitude: 43.2017, longitude: 76.8926 },
  timiryazeva: { latitude: 43.2244, longitude: 76.9139 },
  airport: { latitude: 43.3521, longitude: 77.0405 },
  dostyk: { latitude: 43.2381, longitude: 76.9573 },
  koktobe: { latitude: 43.2306, longitude: 76.9757 },
  rozybakieva: { latitude: 43.2017, longitude: 76.8935 },
  dostykPlaza: { latitude: 43.2334, longitude: 76.9567 },
  driver: { latitude: 43.2506, longitude: 76.9135 },
}

const PLACE_NAMES: [keyof typeof P, string][] = [
  ['abaya', 'ул. Абая, 52'],
  ['esentai', 'Esentai Mall'],
  ['satpaeva', 'Сатпаева, 30'],
  ['mega', 'Mega Alma-Ata'],
  ['timiryazeva', 'Тимирязева, 15'],
  ['airport', 'Аэропорт'],
  ['dostyk', 'Достык, 5'],
  ['koktobe', 'Кок-Тобе'],
  ['rozybakieva', 'Розыбакиева, 247'],
  ['dostykPlaza', 'Dostyk Plaza'],
]

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

const page = (items: unknown[]) => ({ items, limit: 100, offset: 0, total: items.length })

type Api = Record<string, unknown | ((url: URL, body: unknown) => unknown)>

const user = (role: string, username: string) => ({
  user: { id: `${role}-user`, username, role, created_at: '2026-11-03T04:00:00Z' },
  csrf_token: 'csrf',
  expires_at: '2026-11-04T04:00:00Z',
})

const vehicle = { make: 'Toyota', model: 'Camry', color: 'белый', plate_number: '123 ABC 02', year: 2020, car_class: 'comfort' }

function driver(overrides: Record<string, unknown> = {}) {
  return {
    id: 'driver-user',
    full_name: 'Арман Нурланов',
    phone: '+7 701 000 00 00',
    license_number: 'KZ 12345678',
    vehicle,
    approval_status: 'approved',
    approved_at: '2026-11-03T05:00:00Z',
    online: false,
    location: P.driver,
    location_updated_at: NOW,
    missing_fields: [],
    rating: { average: null, count: 0 },
    ...overrides,
  }
}

function ride(overrides: Record<string, unknown> = {}) {
  return {
    id: 'ride-1',
    status: 'assigned',
    passenger_id: 'p-aigerim',
    driver_id: 'driver-user',
    quote_id: 'q-1',
    pickup: P.abaya,
    dropoff: P.esentai,
    route: {
      distance_m: 10_000,
      duration_s: 1500,
      route_geometry: {
        type: 'LineString',
        coordinates: [
          [P.abaya.longitude, P.abaya.latitude],
          [76.921, 43.232],
          [P.esentai.longitude, P.esentai.latitude],
        ],
      },
      provider: 'test',
    },
    tariff: 'economy',
    amount_kzt: 2200,
    currency: 'KZT',
    tariff_version: 'v1',
    created_at: '2026-11-03T08:58:00Z',
    updated_at: NOW,
    assigned_at: '2026-11-03T08:58:30Z',
    arrived_at: null,
    started_at: null,
    completed_at: null,
    cancelled_at: null,
    cancel_reason: null,
    payment_method: 'cash',
    payment_status: 'unpaid',
    driver: null,
    my_rating: null,
    ...overrides,
  }
}

function summary(id: string, from: keyof typeof P, to: keyof typeof P, overrides: Record<string, unknown> = {}) {
  return {
    id,
    status: 'completed',
    passenger_id: 'p-aigerim',
    driver_id: 'driver-user',
    pickup: P[from],
    dropoff: P[to],
    distance_m: 7200,
    duration_s: 1440,
    amount_kzt: 2200,
    currency: 'KZT',
    created_at: '2026-11-03T09:20:00Z',
    updated_at: '2026-11-03T09:40:00Z',
    payment_status: 'paid',
    payment_method: 'kaspi_link',
    ...overrides,
  }
}

/** Today: 3 rides, 6 460 ₸, 1 h 12 min on the road (Figma 6:2, 25:149, 26:577). */
const TODAY = [
  summary('h-1', 'abaya', 'esentai', { created_at: '2026-11-03T09:20:00Z', duration_s: 1500 }),
  summary('h-2', 'satpaeva', 'mega', {
    created_at: '2026-11-03T06:05:00Z',
    amount_kzt: 1840,
    payment_method: 'cash',
    duration_s: 1260,
  }),
  summary('h-3', 'dostyk', 'koktobe', {
    created_at: '2026-11-03T04:40:00Z',
    amount_kzt: 2420,
    payment_method: 'cash',
    payment_status: 'unpaid',
    duration_s: 1560,
  }),
]

async function mockBackend(target: Page, role: 'driver' | 'admin', api: Api) {
  await target.route('https://tiles.openfreemap.org/**', (route) => route.abort())
  await target.route('https://accounts.google.com/**', (route) => route.abort())
  await target.route('https://nominatim.openstreetmap.org/**', (route) => {
    const url = new URL(route.request().url())
    const lat = Number(url.searchParams.get('lat'))
    const lon = Number(url.searchParams.get('lon'))
    const match = PLACE_NAMES.find(([key]) => Math.abs(P[key].latitude - lat) < 1e-6 && Math.abs(P[key].longitude - lon) < 1e-6)
    return json(route, {
      place_id: Math.round(lat * 1e4),
      lat: String(lat),
      lon: String(lon),
      name: match?.[1] ?? 'Точка',
      display_name: match?.[1] ?? 'Точка',
      address: {},
    })
  })
  await target.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/api/v1/auth/session') return json(route, user(role, role === 'admin' ? 'admin' : 'arman'))
    if (url.pathname === '/api/v1/auth/providers') return json(route, { google_client_id: null })
    const key = `${request.method()} ${url.pathname}`
    const handler = api[key] ?? Object.entries(api).find(([pattern]) => new RegExp(`^${pattern}$`).test(key))?.[1]
    if (handler === undefined) {
      if (request.method() === 'PUT' && url.pathname.endsWith('/location')) return json(route, driver({ online: true }))
      return json(route, { error: { code: 'not_found', message: key, details: {} }, request_id: 'visual' }, 404)
    }
    const body = request.postDataJSON() as unknown
    return json(route, typeof handler === 'function' ? handler(url, body) : handler)
  })
}

async function openApp(browser: Browser, viewport: { width: number; height: number }, storage: Record<string, string> = {}) {
  const context = await browser.newContext({
    viewport,
    deviceScaleFactor: 1,
    geolocation: P.driver,
    permissions: ['geolocation'],
    locale: 'ru-RU',
    timezoneId: 'Asia/Almaty',
  })
  const target = await context.newPage()
  // Time flows (Leaflet animations read Date) until `settle` pins it for the countdowns.
  await target.clock.install({ time: new Date(NOW) })
  await target.addInitScript((items) => {
    for (const [key, value] of Object.entries(items)) localStorage.setItem(key, value)
  }, storage)
  return target
}

async function settle(target: Page) {
  await target.evaluate('document.fonts.ready')
  await target.waitForTimeout(1200)
  await target.clock.setFixedTime(new Date(NOW))
  await target.waitForTimeout(1100)
}

interface Comparison {
  frame: string
  name: string
  mismatch: number
}

const results: Comparison[] = []

/** Figma | app | diff (red where a channel differs by more than 24), plus the mismatch share. */
async function compare(browser: Browser, target: Page, name: string, frame: string, desktop = false) {
  const mine = await target.screenshot({ path: path.join(OUT, `${name}.png`) })
  const figmaFile = path.join(FIGMA, `${name}-${frame}.png`)
  const figma = readFileSync(figmaFile).toString('base64')
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 })
  const sheet = await context.newPage()
  const cropTop = desktop ? 0 : STATUS_BAR
  const { width, height } = desktop ? DESKTOP : MOBILE
  await sheet.setContent('<body style="margin:0;background:#fff"></body>')
  const mismatch = await sheet.evaluate(
    async ({ figma, mine, cropTop, width, height }) => {
      const load = (src: string) =>
        new Promise<HTMLImageElement>((resolve) => {
          const image = new Image()
          image.onload = () => resolve(image)
          image.src = src
        })
      const [a, b] = await Promise.all([load(`data:image/png;base64,${figma}`), load(`data:image/png;base64,${mine}`)])
      const canvas = document.createElement('canvas')
      const gap = 16
      canvas.width = width * 3 + gap * 2
      canvas.height = height
      const ctx = canvas.getContext('2d') as CanvasRenderingContext2D
      ctx.fillStyle = '#ff00ff'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(a, 0, cropTop, width, height, 0, 0, width, height)
      ctx.drawImage(b, 0, 0, width, height, width + gap, 0, width, height)
      const pa = ctx.getImageData(0, 0, width, height).data
      const pb = ctx.getImageData(width + gap, 0, width, height).data
      const diff = ctx.createImageData(width, height)
      let bad = 0
      const at = (data: Uint8ClampedArray, index: number) => data[index] ?? 0
      for (let i = 0; i < pa.length; i += 4) {
        let delta = 0
        for (let c = 0; c < 3; c += 1) delta = Math.max(delta, Math.abs(at(pa, i + c) - at(pb, i + c)))
        const off = delta > 24
        if (off) bad += 1
        for (let c = 0; c < 3; c += 1) diff.data[i + c] = off ? (c === 0 ? 255 : 0) : at(pa, i + c) * 0.3 + 178
        diff.data[i + 3] = 255
      }
      ctx.putImageData(diff, (width + gap) * 2, 0)
      document.body.appendChild(canvas)
      return bad / (width * height)
    },
    { figma, mine: mine.toString('base64'), cropTop, width, height },
  )
  await sheet.setViewportSize({ width: width * 3 + 32, height })
  await sheet.locator('canvas').screenshot({ path: path.join(OUT, `compare-${name}.png`) })
  await context.close()
  results.push({ frame, name, mismatch: Math.round(mismatch * 1000) / 10 })
}

test.describe.configure({ mode: 'serial' })
test.setTimeout(90_000)

test.afterAll(() => {
  results.sort((a, b) => a.name.localeCompare(b.name))
  writeFileSync(path.join(OUT, 'driver-admin-summary.json'), `${JSON.stringify(results, null, 2)}\n`)
})

/** `GET /rides` honours the `status` filter, so the active-ride lookup does not pick a finished one. */
const history = (url: URL) => {
  const statuses = url.searchParams.getAll('status')
  return page(statuses.length ? TODAY.filter((item) => statuses.includes(item.status)) : TODAY)
}

const shiftApi = (overrides: Api = {}): Api => ({
  'GET /api/v1/rides': history,
  'GET /api/v1/drivers/me/offers': page([]),
  ...overrides,
})

test('6:2 offline', async ({ browser }) => {
  const target = await openApp(browser, MOBILE)
  await mockBackend(target, 'driver', shiftApi({ 'GET /api/v1/drivers/me': driver() }))
  await target.goto('/driver')
  await expect(target.getByText('6 460', { exact: false })).toBeVisible()
  await settle(target)
  await compare(browser, target, 'driver-offline', '6-2')
})

test('25:2 pending', async ({ browser }) => {
  const target = await openApp(browser, MOBILE)
  await mockBackend(target, 'driver', shiftApi({ 'GET /api/v1/drivers/me': driver({ approval_status: 'pending' }) }))
  await target.goto('/driver')
  await expect(target.getByText('Аккаунт на проверке')).toBeVisible()
  await settle(target)
  await compare(browser, target, 'driver-pending', '25-2')
})

test('25:149 online', async ({ browser }) => {
  const since = String(Date.parse(NOW) - (2 * 60 + 15) * 60_000)
  const target = await openApp(browser, MOBILE, { 'bis.driver.onlineSince': since })
  await mockBackend(target, 'driver', shiftApi({ 'GET /api/v1/drivers/me': driver({ online: true }) }))
  await target.goto('/driver')
  await expect(target.getByText('2 ч 15 мин')).toBeVisible()
  await settle(target)
  await compare(browser, target, 'driver-online', '25-149')
})

test('6:125 new offer', async ({ browser }) => {
  const target = await openApp(browser, MOBILE)
  const offer = {
    id: 'offer-1',
    ride_id: 'ride-1',
    status: 'pending',
    pickup: P.abaya,
    dropoff: P.esentai,
    distance_m: 10_000,
    duration_s: 1500,
    amount_kzt: 2200,
    currency: 'KZT',
    tariff: 'economy',
    passenger_rating: { average: null, count: 0 },
    created_at: '2026-11-03T09:00:00Z',
    expires_at: '2026-11-03T09:00:30Z',
  }
  await mockBackend(
    target,
    'driver',
    shiftApi({
      'GET /api/v1/drivers/me': driver({ online: true, location: { latitude: 43.2507, longitude: 76.915 } }),
      'GET /api/v1/drivers/me/offers': page([offer]),
    }),
  )
  await target.context().setGeolocation({ latitude: 43.2507, longitude: 76.915 })
  await target.goto('/driver')
  await expect(target.getByText('Esentai Mall')).toBeVisible({ timeout: 10_000 })
  await settle(target)
  await compare(browser, target, 'driver-offer', '6-125')
})

const rideApi = (current: Record<string, unknown>, extra: Api = {}): Api =>
  shiftApi({
    'GET /api/v1/drivers/me': driver({ online: true }),
    'GET /api/v1/rides/ride-1': current,
    ...extra,
  })

test('6:243 active ride (assigned)', async ({ browser }) => {
  const target = await openApp(browser, MOBILE, { 'bis.driver.rideId': 'ride-1' })
  await mockBackend(target, 'driver', rideApi(ride()))
  await target.goto('/driver')
  await expect(target.getByText(/ул\. Абая, 52 ·/)).toBeVisible({ timeout: 10_000 })
  await settle(target)
  await compare(browser, target, 'driver-assigned', '6-243')
})

test('25:260 arrived', async ({ browser }) => {
  const target = await openApp(browser, MOBILE, { 'bis.driver.rideId': 'ride-1' })
  await mockBackend(target, 'driver', rideApi(ride({ status: 'arrived', arrived_at: '2026-11-03T08:57:51Z' })))
  await target.goto('/driver')
  await expect(target.getByText('Вы на месте · ожидание 02:15')).toBeVisible()
  await expect(target.getByText(/ул\. Абая, 52 —/)).toBeVisible({ timeout: 10_000 })
  await settle(target)
  await compare(browser, target, 'driver-arrived', '25-260')
})

test('25:359 in progress (Kaspi)', async ({ browser }) => {
  const target = await openApp(browser, MOBILE, { 'bis.driver.rideId': 'ride-1' })
  const route = { ...ride().route, distance_m: 7200, duration_s: 1080 }
  await mockBackend(
    target,
    'driver',
    rideApi(ride({ status: 'in_progress', payment_method: 'kaspi_link', payment_status: 'paid', route })),
  )
  await target.goto('/driver')
  await expect(target.getByText('Едьте в Esentai Mall')).toBeVisible({ timeout: 10_000 })
  await settle(target)
  await compare(browser, target, 'driver-in-progress', '25-359')
})

test('25:497 release with a reason', async ({ browser }) => {
  const target = await openApp(browser, MOBILE, { 'bis.driver.rideId': 'ride-1' })
  await mockBackend(target, 'driver', rideApi(ride({ status: 'arrived', arrived_at: '2026-11-03T08:57:51Z' })))
  await target.goto('/driver')
  await target.getByRole('button', { name: 'Отказаться от заказа' }).click()
  await target.getByRole('button', { name: 'Пассажир не вышел' }).click()
  await settle(target)
  await compare(browser, target, 'driver-release', '25-497')
})

test('26:425 passenger cancelled', async ({ browser }) => {
  const target = await openApp(browser, MOBILE, { 'bis.driver.rideId': 'ride-1' })
  await mockBackend(target, 'driver', rideApi(ride({ status: 'cancelled', cancelled_at: NOW })))
  await target.goto('/driver')
  await expect(target.getByText('Пассажир отменил поездку')).toBeVisible()
  await settle(target)
  await compare(browser, target, 'driver-cancelled', '26-425')
})

test('13:442 collect cash', async ({ browser }) => {
  const target = await openApp(browser, MOBILE, { 'bis.driver.rideId': 'ride-1' })
  await mockBackend(
    target,
    'driver',
    rideApi(ride({ status: 'completed', completed_at: NOW }), {
      'GET /api/v1/rides/ride-1/payment': { ride_id: 'ride-1', amount_kzt: 2200, currency: 'KZT', method: 'cash', status: 'unpaid', paid_at: null, refunded_at: null, payment_url: null },
    }),
  )
  await target.goto('/driver')
  await expect(target.getByText('Esentai Mall')).toBeVisible({ timeout: 10_000 })
  await settle(target)
  await compare(browser, target, 'driver-cash', '13-442')
})

test('25:464 completed Kaspi with the rating', async ({ browser }) => {
  const target = await openApp(browser, MOBILE, { 'bis.driver.rideId': 'ride-1' })
  await mockBackend(
    target,
    'driver',
    rideApi(ride({ status: 'completed', completed_at: NOW, payment_method: 'kaspi_link', payment_status: 'paid' })),
  )
  await target.goto('/driver')
  await target.getByRole('button', { name: 'Вовремя' }).click()
  await target.getByRole('button', { name: 'Вежливый' }).click()
  await target.mouse.move(0, 0)
  await settle(target)
  await compare(browser, target, 'driver-completed-kaspi', '25-464')
})

test('6:348 profile', async ({ browser }) => {
  const target = await openApp(browser, MOBILE)
  await mockBackend(target, 'driver', shiftApi({ 'GET /api/v1/drivers/me': driver({ approval_status: 'pending' }) }))
  await target.goto('/driver/profile')
  await expect(target.getByText('На проверке')).toBeVisible()
  await settle(target)
  await compare(browser, target, 'driver-profile', '6-348')
})

test('26:500 settings', async ({ browser }) => {
  const target = await openApp(browser, MOBILE)
  await mockBackend(
    target,
    'driver',
    shiftApi({
      'GET /api/v1/drivers/me': driver({ vehicle: { ...vehicle, color: 'Серо-синий', plate_number: '123ABC02' } }),
    }),
  )
  await target.goto('/driver/settings')
  await expect(target.getByRole('heading', { name: 'Настройки' })).toBeVisible()
  await settle(target)
  await compare(browser, target, 'driver-settings', '26-500')
})

test('26:577 history', async ({ browser }) => {
  const target = await openApp(browser, MOBILE)
  await mockBackend(target, 'driver', shiftApi({ 'GET /api/v1/drivers/me': driver() }))
  await target.goto('/driver/history')
  await expect(target.getByText(/Кок-Тобе/)).toBeVisible({ timeout: 15_000 })
  await settle(target)
  await compare(browser, target, 'driver-history', '26-577')
})

const adminDriver = (id: string, name: string, car: Record<string, unknown>, overrides: Record<string, unknown> = {}) => ({
  ...driver({ id, full_name: name, approval_status: 'pending', approved_at: null, vehicle: { ...vehicle, ...car } }),
  username: id,
  created_at: '2026-11-03T04:00:00Z',
  approved_by: null,
  ...overrides,
})

const ADMIN_DRIVERS = [
  adminDriver('arman', 'Арман Нурланов', { plate_number: '123ABC02' }),
  adminDriver('daniyar', 'Данияр С.', { make: 'Hyundai', model: 'Elantra', color: 'серый', plate_number: '777KZ02' }),
  adminDriver('erlan', 'Ерлан К.', { make: 'Kia', model: 'K5', color: 'чёрный', plate_number: '505AAA02' }),
]

const USERS = [
  { id: 'p-aigerim', username: 'aigerim', role: 'passenger', display_name: 'Айгерим', created_at: '2026-11-03T04:00:00Z' },
  { id: 'arman', username: 'arman', role: 'driver', display_name: 'Арман Нурланов', created_at: '2026-11-03T04:00:00Z' },
  { id: 'daniyar', username: 'daniyar', role: 'driver', display_name: 'Данияр С.', created_at: '2026-11-03T04:00:00Z' },
  { id: 'p-olzhas', username: 'olzhas', role: 'passenger', display_name: 'Олжас', created_at: '2026-11-03T04:00:00Z' },
  { id: 'admin-user', username: 'admin', role: 'admin', display_name: null, created_at: '2026-11-03T04:00:00Z' },
]

const MORE_USERS = [
  { id: 'p-dana', username: 'dana', role: 'passenger', display_name: 'Дана', created_at: '2026-11-03T04:00:00Z' },
  { id: 'p-madina', username: 'madina', role: 'passenger', display_name: 'Мадина', created_at: '2026-11-03T04:00:00Z' },
  { id: 'p-erzhan', username: 'erzhan', role: 'passenger', display_name: 'Ержан', created_at: '2026-11-03T04:00:00Z' },
  { id: 'erlan', username: 'erlan', role: 'driver', display_name: 'Ерлан К.', created_at: '2026-11-03T04:00:00Z' },
]

const ADMIN_RIDES = [
  summary('r-1', 'abaya', 'esentai', { status: 'in_progress', driver_id: 'arman', payment_method: 'cash', payment_status: 'unpaid' }),
  summary('r-2', 'satpaeva', 'mega', { status: 'searching', passenger_id: 'p-dana', driver_id: null, amount_kzt: 1840, payment_method: 'cash', payment_status: 'unpaid' }),
  summary('r-3', 'timiryazeva', 'airport', { passenger_id: 'p-olzhas', driver_id: 'daniyar', amount_kzt: 4900 }),
  summary('r-4', 'dostyk', 'koktobe', { status: 'cancelled', passenger_id: 'p-madina', driver_id: null, payment_method: null, payment_status: null }),
  summary('r-5', 'rozybakieva', 'dostykPlaza', { passenger_id: 'p-erzhan', driver_id: 'erlan', amount_kzt: 1120, payment_method: 'cash' }),
]

const adminApi: Api = {
  'GET /api/v1/admin/drivers': (url: URL) =>
    url.searchParams.get('approval_status') === 'approved' ? page([]) : page(ADMIN_DRIVERS),
  'GET /api/v1/admin/users': (url: URL) =>
    url.searchParams.get('limit') === '100' && !url.searchParams.get('role')
      ? page([...USERS, ...MORE_USERS])
      : page(USERS),
  'GET /api/v1/admin/rides': page(ADMIN_RIDES),
}

test('6:444 admin driver approvals', async ({ browser }) => {
  const target = await openApp(browser, MOBILE)
  await mockBackend(target, 'admin', adminApi)
  await target.goto('/admin')
  await expect(target.getByText('Ерлан К.')).toBeVisible()
  await settle(target)
  await compare(browser, target, 'admin-drivers', '6-444')
})

test('26:764 admin driver card', async ({ browser }) => {
  const target = await openApp(browser, MOBILE)
  await mockBackend(target, 'admin', {
    ...adminApi,
    'GET /api/v1/admin/drivers': page([adminDriver('arman', 'Арман Нурланов', { color: 'серо-синий', plate_number: '123ABC02' })]),
  })
  await target.goto('/admin/drivers/arman')
  await expect(target.getByText('Все обязательные поля заполнены')).toBeVisible()
  await settle(target)
  await compare(browser, target, 'admin-driver-card', '26-764')
})

test('26:655 admin people', async ({ browser }) => {
  const target = await openApp(browser, MOBILE)
  await mockBackend(target, 'admin', adminApi)
  await target.goto('/admin/users')
  await expect(target.getByText('@olzhas')).toBeVisible()
  await settle(target)
  await compare(browser, target, 'admin-users', '26-655')
})

test('6:534 admin rides', async ({ browser }) => {
  const target = await openApp(browser, MOBILE)
  await mockBackend(target, 'admin', { ...adminApi, 'GET /api/v1/admin/rides': page(ADMIN_RIDES.slice(0, 4)) })
  await target.goto('/admin/rides')
  await expect(target.locator('li').getByText(/Кок-Тобе/)).toBeVisible({ timeout: 20_000 })
  await settle(target)
  await compare(browser, target, 'admin-rides', '6-534')
})

test('7:111 admin rides, desktop', async ({ browser }) => {
  const target = await openApp(browser, DESKTOP)
  await mockBackend(target, 'admin', adminApi)
  await target.goto('/admin/rides')
  await expect(target.getByText(/Dostyk Plaza/).last()).toBeVisible({ timeout: 25_000 })
  await settle(target)
  await compare(browser, target, 'admin-rides-desktop', '7-111', true)
})

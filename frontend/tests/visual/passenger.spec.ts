import { mkdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { test, type Page, type Route } from '@playwright/test'

/**
 * Passenger screens next to the Figma frames (fileKey 6VHeDBRKk6RWdTYqH0r66K).
 * The API and Nominatim are mocked; map tiles are blocked, so the map is the plain land colour.
 * Output: screenshots/passenger-*.png (the page) and compare/passenger-*.png (Figma | page).
 * The mockups include a 47px iPhone status bar; the page reserves that space itself,
 * so the page is 390×844 and compared with the whole Figma frame.
 */

const HERE = import.meta.dirname
const SHOTS = path.join(HERE, 'screenshots')
const COMPARE = path.join(HERE, 'compare')
mkdirSync(SHOTS, { recursive: true })
mkdirSync(COMPARE, { recursive: true })

const STATUS_BAR = 0
/** 14:20 in Almaty (UTC+5) on 3 November 2026. */
const NOW = Date.parse('2026-11-03T09:20:00Z')
const iso = (offsetS: number, base = NOW) => new Date(base + offsetS * 1000).toISOString()

const PICKUP = { latitude: 43.2545, longitude: 76.936 }
const DROPOFF = { latitude: 43.21834, longitude: 76.92763 }
const DRIVER_NEAR = { latitude: 43.2545 + 0.0115, longitude: 76.936 }

interface NominatimPlace {
  lat: number
  lon: number
  name: string
  road?: string
  house?: string
}

const PLACES: NominatimPlace[] = [
  { lat: PICKUP.latitude, lon: PICKUP.longitude, name: '', road: 'ул. Абая', house: '52' },
  { lat: DROPOFF.latitude, lon: DROPOFF.longitude, name: 'Esentai Mall', road: 'пр. Аль-Фараби', house: '77/8' },
  { lat: 43.20187, lon: 76.89207, name: 'Mega Alma-Ata', road: 'пр. Розыбакиева', house: '247А' },
  { lat: 43.3521, lon: 77.0405, name: 'Аэропорт Алматы', road: 'ул. Майлина', house: '2' },
  { lat: 43.2333, lon: 76.9566, name: 'Dostyk Plaza', road: 'пр. Достык', house: '111' },
]

const SEARCH_RESULTS: NominatimPlace[] = [
  { lat: 43.21763, lon: 76.936, name: 'Esentai Mall', road: 'пр. Аль-Фараби', house: '77/8' },
  { lat: 43.21673, lon: 76.936, name: 'Esentai Tower', road: 'пр. Аль-Фараби', house: '77/7' },
  { lat: 43.20954, lon: 76.936, name: 'Esentai Park', road: 'ул. Жамакаева' },
  { lat: 43.21583, lon: 76.936, name: 'Esentai Apartments', road: 'пр. Аль-Фараби', house: '77' },
]

function nominatim(place: NominatimPlace, index: number) {
  return {
    place_id: 1000 + index,
    lat: String(place.lat),
    lon: String(place.lon),
    name: place.name,
    display_name: [place.name, place.road, 'Алматы'].filter(Boolean).join(', '),
    address: { road: place.road, house_number: place.house, city: 'Алматы' },
  }
}

const ROUTE = {
  distance_m: 10_000,
  duration_s: 1500,
  provider: 'openrouteservice',
  route_geometry: {
    type: 'LineString',
    coordinates: [
      [PICKUP.longitude, PICKUP.latitude],
      [76.931, 43.245],
      [76.941, 43.232],
      [DROPOFF.longitude, DROPOFF.latitude],
    ],
  },
}

const QUOTE = {
  quote_id: '11111111-1111-4111-8111-111111111111',
  pickup: PICKUP,
  dropoff: DROPOFF,
  route: ROUTE,
  options: [
    { tariff: 'economy', amount_kzt: 2200 },
    { tariff: 'comfort', amount_kzt: 2925 },
    { tariff: 'comfort_plus', amount_kzt: 3650 },
    { tariff: 'business', amount_kzt: 4800 },
  ],
  currency: 'KZT',
  tariff_version: 'edu-v2',
  kaspi_payment_url: 'https://pay.kaspi.kz/pay/visual-test',
  created_at: iso(0),
  expires_at: iso(600),
}

const DRIVER = {
  full_name: 'Арман Нурланов',
  phone: '+77011234567',
  vehicle: { make: 'Toyota', model: 'Camry', color: 'серо-синий', plate_number: '123 ABC 02', car_class: 'comfort' },
  location: DRIVER_NEAR,
  location_updated_at: iso(-5),
  rating: { average: 4.9, count: 120 },
}

type Ride = Record<string, unknown>

function ride(overrides: Ride = {}): Ride {
  return {
    id: '22222222-2222-4222-8222-222222222222',
    status: 'searching',
    passenger_id: '33333333-3333-4333-8333-333333333333',
    driver_id: null,
    quote_id: QUOTE.quote_id,
    pickup: PICKUP,
    dropoff: DROPOFF,
    route: ROUTE,
    tariff: 'economy',
    amount_kzt: 2200,
    currency: 'KZT',
    tariff_version: 'edu-v2',
    created_at: iso(-65),
    updated_at: iso(-5),
    assigned_at: null,
    arrived_at: null,
    started_at: null,
    completed_at: null,
    cancelled_at: null,
    cancel_reason: null,
    payment_method: 'kaspi_link',
    payment_status: 'unpaid',
    driver: null,
    my_rating: null,
    ...overrides,
  }
}

function summary(r: Ride): Ride {
  const { route, driver, my_rating, quote_id, tariff_version, ...rest } = r as Ride & { route: typeof ROUTE }
  void driver
  void my_rating
  void quote_id
  void tariff_version
  return { ...rest, distance_m: route.distance_m, duration_s: route.duration_s }
}

const HISTORY: Ride[] = [
  summary(ride({ id: 'h1', status: 'completed', payment_method: 'cash', payment_status: 'paid', created_at: iso(0) })),
  summary(
    ride({
      id: 'h2',
      status: 'completed',
      amount_kzt: 1840,
      payment_method: 'kaspi_link',
      payment_status: 'unpaid',
      dropoff: { latitude: 43.20187, longitude: 76.89207 },
      created_at: iso(-5 * 3600 - 15 * 60),
    }),
  ),
  summary(
    ride({
      id: 'h3',
      status: 'cancelled',
      payment_method: 'cash',
      payment_status: 'unpaid',
      dropoff: { latitude: 43.3521, longitude: 77.0405 },
      created_at: iso(-15 * 3600 - 39 * 60),
    }),
  ),
  summary(
    ride({
      id: 'h4',
      status: 'completed',
      amount_kzt: 1120,
      payment_method: 'cash',
      payment_status: 'paid',
      dropoff: { latitude: 43.2333, longitude: 76.9566 },
      created_at: iso(-20 * 3600 - 10 * 60),
    }),
  ),
]

interface Scenario {
  /** Active ride for `GET /rides?status=…&limit=1` and the ride of `GET /rides/{id}` (one per poll). */
  rides?: Ride[]
  history?: Ride[]
  quote?: { status: number; body: unknown }
  now?: number
}

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

function nearest(lat: number, lon: number): NominatimPlace {
  const distance = (place: NominatimPlace) => (place.lat - lat) ** 2 + (place.lon - lon) ** 2
  return PLACES.reduce((best, place) => (distance(place) < distance(best) ? place : best))
}

async function mock(page: Page, scenario: Scenario) {
  const rides = scenario.rides ?? []
  let polls = 0
  // Time flows from NOW: a frozen clock (setFixedTime) would stall Leaflet's pan animations.
  await page.clock.setSystemTime(scenario.now ?? NOW)
  await page.route('https://tiles.openfreemap.org/**', (route) => route.abort())
  await page.route('https://accounts.google.com/**', (route) => route.abort())
  await page.route('https://nominatim.openstreetmap.org/**', (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === '/reverse') {
      const place = nearest(Number(url.searchParams.get('lat')), Number(url.searchParams.get('lon')))
      return json(route, nominatim(place, PLACES.indexOf(place)))
    }
    return json(route, SEARCH_RESULTS.map(nominatim))
  })
  await page.route('**/api/v1/**', (route) => {
    const url = new URL(route.request().url())
    const method = route.request().method()
    const p = url.pathname
    if (p === '/api/v1/auth/session') {
      return json(route, {
        user: { id: 'u1', username: 'aigerim', role: 'passenger', created_at: iso(-86400 * 30) },
        csrf_token: 'csrf',
        expires_at: iso(86400),
      })
    }
    if (p === '/api/v1/auth/providers') return json(route, { google_client_id: null })
    if (p === '/api/v1/users/me') {
      return json(route, {
        id: 'u1',
        username: 'aigerim',
        role: 'passenger',
        created_at: iso(-86400 * 30),
        display_name: 'Айгерим Жумабаева',
        phone: '+7 701 123 45 67',
        rating: { average: 4.8, count: 12 },
      })
    }
    if (p === '/api/v1/rides/quotes' && method === 'POST') {
      const quote = scenario.quote ?? { status: 200, body: QUOTE }
      return json(route, quote.body, quote.status)
    }
    if (p === '/api/v1/rides' && method === 'GET') {
      if (url.searchParams.get('limit') === '1') {
        return json(route, { items: [], limit: 1, offset: 0, total: 0 })
      }
      const items = scenario.history ?? []
      return json(route, { items, limit: 20, offset: 0, total: items.length })
    }
    const match = /^\/api\/v1\/rides\/([^/]+)$/.exec(p)
    if (match && method === 'GET') {
      const current = rides[Math.min(polls, rides.length - 1)]
      polls += 1
      return current ? json(route, current) : json(route, { error: { code: 'ride_not_found', message: 'x', details: {} } }, 404)
    }
    return json(route, { error: { code: 'not_found', message: 'Not mocked', details: {} } }, 404)
  })
}

async function settle(page: Page, ms = 900) {
  await page.evaluate('document.fonts.ready')
  await page.waitForTimeout(ms)
}

async function shootAndCompare(page: Page, name: string, figma: string) {
  const viewport = page.viewportSize() ?? { width: 390, height: 844 }
  const shot = path.join(SHOTS, `passenger-${name}.png`)
  await page.screenshot({ path: shot })
  const app = readFileSync(shot).toString('base64')
  const reference = readFileSync(path.join(HERE, 'figma', figma)).toString('base64')
  const mobile = viewport.width < 1024
  const crop = mobile ? STATUS_BAR : 0
  const compare = await page.context().newPage()
  await compare.setViewportSize({ width: viewport.width * 2 + 24, height: viewport.height + 20 })
  await compare.setContent(`
    <body style="margin:0;background:#ddd;font:12px/20px sans-serif;display:flex;gap:24px;overflow:hidden">
      <figure style="margin:0"><figcaption>Figma ${figma}</figcaption>
        <div style="width:${viewport.width}px;height:${viewport.height}px;overflow:hidden;background:#fff">
          <img style="display:block;margin-top:-${crop}px;width:${viewport.width}px" src="data:image/png;base64,${reference}"></div></figure>
      <figure style="margin:0"><figcaption>Страница</figcaption>
        <img style="display:block" src="data:image/png;base64,${app}"></figure>
    </body>`)
  await compare.screenshot({ path: path.join(COMPARE, `passenger-${name}.png`) })
  await compare.close()
}

test.describe('passenger 390px', () => {
  test.use({ viewport: { width: 390, height: 844 }, geolocation: PICKUP, permissions: ['geolocation'] })

  test('home 4:94', async ({ page }) => {
    await mock(page, {})
    await page.goto('/')
    await page.getByRole('heading', { name: 'Куда едем?' }).waitFor()
    await settle(page)
    await shootAndCompare(page, 'home-4-94', 'passenger-home-4-94.png')
  })

  test('address search 23:2', async ({ page }) => {
    await mock(page, {})
    await page.goto('/')
    await page.getByRole('button', { name: 'Куда едем?' }).click()
    await page.getByRole('textbox', { name: 'Куда' }).fill('Esent')
    await page.getByText('Esentai Apartments').waitFor()
    await page.getByText(/Моё местоположение · ул\. Абая/).waitFor()
    await settle(page)
    await shootAndCompare(page, 'address-search-23-2', 'passenger-address-search-23-2.png')
  })

  test('map point 23:97', async ({ page }) => {
    await mock(page, {})
    await page.goto('/')
    await page.getByRole('button', { name: /Esentai Mall/ }).click()
    await page.getByRole('button', { name: 'Назад' }).click()
    await page.getByRole('button', { name: /Точка на карте/ }).click()
    await page.getByText('пр. Аль-Фараби, 77/8').waitFor({ timeout: 10_000 })
    await settle(page)
    await shootAndCompare(page, 'map-point-23-97', 'passenger-map-point-23-97.png')
  })

  async function openChoose(page: Page, scenario: Scenario) {
    await mock(page, scenario)
    await page.goto('/')
    await page.getByRole('button', { name: /Esentai Mall/ }).click()
  }

  test('choose ride 4:253', async ({ page }) => {
    await openChoose(page, {})
    await page.getByRole('radio', { name: /Kaspi/ }).click()
    await page.getByRole('button', { name: 'Заказать Эконом · Kaspi' }).waitFor()
    await page.getByText('ул. Абая, 52').first().waitFor()
    await settle(page)
    await shootAndCompare(page, 'choose-ride-4-253', 'passenger-choose-ride-4-253.png')
  })

  test('route error 24:897', async ({ page }) => {
    await openChoose(page, {
      quote: { status: 503, body: { error: { code: 'routing_unavailable', message: 'x', details: {} } } },
    })
    await page.getByRole('heading', { name: 'Не удалось построить маршрут' }).waitFor()
    await settle(page)
    await shootAndCompare(page, 'route-error-24-897', 'passenger-route-error-24-897.png')
  })

  const assigned = (overrides: Ride = {}) =>
    ride({ status: 'assigned', driver_id: 'd1', driver: DRIVER, assigned_at: iso(-20), payment_status: 'paid', ...overrides })

  const rideScreens: [string, string, Ride[], string | RegExp, number?][] = [
    ['searching-5-268', 'passenger-searching-5-268.png', [ride()], 'Подбираем ближайшего водителя'],
    ['driver-found-paid-23-191', 'passenger-driver-found-paid-23-191.png', [assigned()], 'Водитель найден'],
    ['no-driver-23-391', 'passenger-no-driver-23-391.png', [ride({ status: 'no_driver' })], 'Свободных водителей нет'],
    [
      'arrived-24-351',
      'passenger-arrived-24-351.png',
      [assigned({ status: 'arrived', arrived_at: iso(-15), driver: { ...DRIVER, location: { latitude: 43.2549, longitude: 76.9368 } } })],
      'Выходите — вас ждут',
    ],
    [
      'in-progress-24-451',
      'passenger-in-progress-24-451.png',
      [
        assigned({
          status: 'in_progress',
          started_at: iso(0),
          driver: { ...DRIVER, location: { latitude: 43.244, longitude: 76.933 } },
        }),
      ],
      /Прибытие ~14:45/,
      NOW + 7 * 60_000,
    ],
    [
      'cancelled-24-633',
      'passenger-cancelled-24-633.png',
      [ride({ status: 'cancelled', payment_status: 'refunded', cancelled_at: iso(-10) })],
      'Поездка отменена',
    ],
    [
      'completed-cash-24-668',
      'passenger-completed-cash-24-668.png',
      [ride({ status: 'completed', payment_method: 'cash', payment_status: 'unpaid', completed_at: iso(0) })],
      'Оплатите наличными',
    ],
  ]

  for (const [name, figma, rides, heading, now] of rideScreens) {
    test(`ride ${name}`, async ({ page }) => {
      await mock(page, { rides, now })
      if (name.startsWith('completed-cash')) {
        await page.addInitScript((driver) => {
          sessionStorage.setItem('bis.rideDriver:22222222-2222-4222-8222-222222222222', JSON.stringify(driver))
        }, DRIVER)
      }
      await page.goto('/ride/22222222-2222-4222-8222-222222222222')
      await page.getByRole('heading', { name: heading }).waitFor()
      await settle(page, 2600)
      await shootAndCompare(page, name, figma)
    })
  }

  test('driver on the way 5:370', async ({ page }) => {
    await mock(page, { rides: [assigned({ payment_method: 'cash', payment_status: 'unpaid' })] })
    await page.goto('/ride/22222222-2222-4222-8222-222222222222')
    await page.getByRole('heading', { name: /Приедет через/ }).waitFor()
    await settle(page, 2600)
    await shootAndCompare(page, 'driver-on-way-5-370', 'passenger-driver-on-way-5-370.png')
  })

  test('cancel confirm 24:555', async ({ page }) => {
    await mock(page, { rides: [assigned()] })
    await page.addInitScript(() => sessionStorage.setItem('bis.driverFoundSeen:22222222-2222-4222-8222-222222222222', '1'))
    await page.goto('/ride/22222222-2222-4222-8222-222222222222')
    await page.getByRole('button', { name: 'Отменить' }).click()
    await page.getByRole('heading', { name: 'Отменить поездку?' }).waitFor()
    await settle(page, 2600)
    await shootAndCompare(page, 'cancel-confirm-24-555', 'passenger-cancel-confirm-24-555.png')
  })

  test('driver declined 23:281', async ({ page }) => {
    await mock(page, { rides: [assigned(), ride({ payment_status: 'paid' })] })
    await page.addInitScript(() => sessionStorage.setItem('bis.driverFoundSeen:22222222-2222-4222-8222-222222222222', '1'))
    await page.goto('/ride/22222222-2222-4222-8222-222222222222')
    await page.getByRole('heading', { name: 'Подбираем другого водителя' }).waitFor({ timeout: 10_000 })
    await settle(page, 2600)
    await shootAndCompare(page, 'driver-declined-23-281', 'passenger-driver-declined-23-281.png')
  })

  test('ride completed 5:499', async ({ page }) => {
    await mock(page, { rides: [ride({ status: 'completed', payment_status: 'paid', completed_at: iso(0) })] })
    await page.addInitScript((driver) => {
      sessionStorage.setItem('bis.rideDriver:22222222-2222-4222-8222-222222222222', JSON.stringify(driver))
    }, DRIVER)
    await page.goto('/ride/22222222-2222-4222-8222-222222222222')
    await page.getByRole('heading', { name: 'Поездка завершена' }).waitFor()
    await page.getByRole('radio', { name: '4 из 5' }).click()
    await page.getByRole('button', { name: 'Вежливый' }).click()
    await page.getByRole('button', { name: 'Чисто' }).click()
    await page.getByText('Esentai Mall · 25 мин').waitFor()
    await settle(page, 2600)
    await shootAndCompare(page, 'completed-5-499', 'passenger-completed-5-499.png')
  })

  test('ride details 24:708', async ({ page }) => {
    await mock(page, {
      rides: [
        ride({
          status: 'completed',
          payment_status: 'paid',
          created_at: iso(0),
          started_at: iso(0),
          completed_at: iso(25 * 60),
          my_rating: { stars: 5, tags: ['polite'], comment: null },
        }),
      ],
    })
    await page.addInitScript((driver) => {
      sessionStorage.setItem('bis.rideDriver:22222222-2222-4222-8222-222222222222', JSON.stringify(driver))
    }, DRIVER)
    await page.goto('/history/22222222-2222-4222-8222-222222222222')
    await page.getByText('Тариф').waitFor()
    await page.getByText('Esentai Mall').waitFor()
    await settle(page, 2600)
    await shootAndCompare(page, 'ride-details-24-708', 'passenger-ride-details-24-708.png')
  })

  test('history 5:550', async ({ page }) => {
    await mock(page, { history: HISTORY })
    await page.goto('/history')
    await page.getByText('Dostyk Plaza').waitFor()
    await settle(page)
    await shootAndCompare(page, 'history-5-550', 'passenger-history-5-550.png')
  })

  test('empty history 24:826', async ({ page }) => {
    await mock(page, { history: [] })
    await page.goto('/history')
    await page.getByText('Поездок пока нет').waitFor()
    await settle(page)
    await shootAndCompare(page, 'empty-history-24-826', 'passenger-empty-history-24-826.png')
  })

  test('profile 5:623', async ({ page }) => {
    await mock(page, {})
    await page.goto('/profile')
    await page.getByRole('link', { name: /Айгерим Жумабаева/ }).waitFor()
    await settle(page)
    await shootAndCompare(page, 'profile-5-623', 'passenger-profile-5-623.png')
  })

  test('settings 12:604', async ({ page }) => {
    await mock(page, {})
    await page.goto('/profile/settings')
    await page.getByRole('button', { name: 'Сохранить' }).waitFor()
    await settle(page)
    await shootAndCompare(page, 'settings-12-604', 'passenger-settings-12-604.png')
  })
})

test.describe('passenger 1440px', () => {
  test.use({ viewport: { width: 1440, height: 900 }, geolocation: PICKUP, permissions: ['geolocation'] })

  test('desktop choose ride 7:2', async ({ page }) => {
    await mock(page, {})
    await page.goto('/')
    await page.getByRole('button', { name: /Esentai Mall/ }).click()
    await page.getByRole('radio', { name: /Kaspi/ }).click()
    await page.getByRole('heading', { name: 'Заказать поездку' }).waitFor()
    await page.getByRole('button', { name: /ул\. Абая, 52/ }).waitFor()
    await settle(page)
    await shootAndCompare(page, 'desktop-7-2', 'desktop-7-2.png')
  })
})

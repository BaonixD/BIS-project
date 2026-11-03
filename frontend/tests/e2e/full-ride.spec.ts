import { mkdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test, type Browser, type BrowserContext, type Page } from '@playwright/test'
import { DEMO_PASSWORD } from './env.ts'

/**
 * A whole ride on the real backend, a passenger and a driver side by side (390×844 each).
 * The passenger stands at the demo pickup in central Almaty; demo_driver_1 (economy) is ~250 m north,
 * the nearest driver, so the dispatcher offers him the order first.
 * Every key step is saved to screenshots/NN-<figma frame>.png and, next to the Figma frame,
 * to compare/NN-<figma frame>.png. The map is real (CARTO tiles, openrouteservice route).
 */

const HERE = import.meta.dirname
const SHOTS = path.join(HERE, 'screenshots')
const COMPARE = path.join(HERE, 'compare')
const FIGMA = path.join(HERE, '..', 'visual', 'figma')
mkdirSync(SHOTS, { recursive: true })
mkdirSync(COMPARE, { recursive: true })

const VIEWPORT = { width: 390, height: 844 }
/** seeds/demo.py DEMO_PICKUP. */
const PICKUP = { latitude: 43.2383, longitude: 76.9457 }
const DRIVER_POINT = { latitude: 43.2405, longitude: 76.9457 }

/** Statuses arrive by polling every 3 s; the dispatcher ticks every second. */
const STEP = { timeout: 30_000 }

interface Shot {
  file: string
  figma: string
}

const shots: Shot[] = []

async function settle(page: Page, ms = 1500) {
  await page.evaluate('document.fonts.ready')
  await page.waitForTimeout(ms)
}

/** `figma` — the frame file in tests/visual/figma without `.png`, e.g. `driver-offer-6-125`. */
async function shoot(page: Page, step: string, figma: string) {
  await settle(page)
  const file = `${step}-${figma}.png`
  await page.screenshot({ path: path.join(SHOTS, file) })
  shots.push({ file, figma: `${figma}.png` })
}

/** Figma | e2e, both 390×844 (the Figma frames include a 47px phone status bar the page does not have). */
async function compose(browser: Browser) {
  const page = await browser.newPage({ viewport: { width: VIEWPORT.width * 2 + 24, height: VIEWPORT.height + 20 } })
  for (const { file, figma } of shots.splice(0)) {
    const app = readFileSync(path.join(SHOTS, file)).toString('base64')
    const reference = readFileSync(path.join(FIGMA, figma)).toString('base64')
    await page.setContent(`
      <body style="margin:0;background:#ddd;font:12px/20px sans-serif;display:flex;gap:24px;overflow:hidden">
        <figure style="margin:0"><figcaption>Figma ${figma}</figcaption>
          <img style="display:block;width:${VIEWPORT.width}px" src="data:image/png;base64,${reference}"></figure>
        <figure style="margin:0"><figcaption>e2e ${file}</figcaption>
          <img style="display:block;width:${VIEWPORT.width}px" src="data:image/png;base64,${app}"></figure>
      </body>`)
    await page.screenshot({ path: path.join(COMPARE, file) })
  }
  await page.close()
}

async function phone(browser: Browser, geolocation: typeof PICKUP): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ viewport: VIEWPORT, geolocation, permissions: ['geolocation'] })
  return { context, page: await context.newPage() }
}

async function login(page: Page, username: string, home: RegExp) {
  await page.goto('/login')
  await page.locator('input[name="username"]').fill(username)
  await page.locator('input[name="password"]').fill(DEMO_PASSWORD)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await page.waitForURL(home)
}

/** demo_driver_1 is seeded online; leave the line first to go online from the shift screen. */
async function driverOnline(page: Page, step: string | null) {
  await login(page, 'demo_driver_1', /\/driver$/)
  const goOnline = page.getByRole('button', { name: 'Выйти на линию' })
  const leave = page.getByRole('button', { name: 'Уйти с линии' })
  await expect(goOnline.or(leave)).toBeVisible()
  if (step === null) {
    if (await goOnline.isVisible()) await goOnline.click()
    await expect(page.getByText('Ищем заказы рядом')).toBeVisible()
    return
  }
  if (await leave.isVisible()) await leave.click()
  await expect(goOnline).toBeEnabled()
  await shoot(page, `${step}a`, 'driver-offline-6-2')
  await goOnline.click()
  await expect(page.getByText('Ищем заказы рядом')).toBeVisible()
  await shoot(page, `${step}b`, 'driver-online-25-149')
}

/** Nominatim answers at most once a second; give the reverse geocoding a moment before a screenshot. */
async function addressesResolved(page: Page) {
  const placeholder = page.getByText(/^Точка (подачи|назначения)$/).first()
  await placeholder.waitFor({ state: 'hidden', timeout: 8_000 }).catch(() => undefined)
}

async function expectFourTariffs(page: Page) {
  const tariffs = page.getByRole('radiogroup', { name: 'Тариф' }).getByRole('radio')
  await expect(tariffs).toHaveCount(4, STEP)
  await expect(tariffs.nth(0)).toContainText('Эконом')
  await page.getByRole('radio', { name: /Эконом/ }).click()
}

test.describe.configure({ mode: 'serial' })

test.afterEach(async ({ browser }) => {
  await compose(browser)
})

test('cash ride: order, offer, the whole trip, cash and ratings', async ({ browser }) => {
  const driver = await phone(browser, DRIVER_POINT)
  const passenger = await phone(browser, PICKUP)
  const d = driver.page
  const p = passenger.page

  await driverOnline(d, '01')

  await login(p, 'demo_passenger_1', /\/$/)
  await expect(p.getByRole('heading', { name: 'Куда едем?' })).toBeVisible()
  await shoot(p, '02', 'passenger-home-4-94')

  await p.getByRole('button', { name: 'Куда едем?' }).click()
  await p.getByRole('textbox', { name: 'Куда' }).fill('Esentai Mall')
  // A Nominatim result carries the distance; the popular «Esentai Mall» row of the home sheet does not.
  const result = p.getByRole('button', { name: /Esentai Mall.*км/ }).first()
  await expect(result).toBeVisible(STEP)
  await shoot(p, '03', 'passenger-address-search-23-2')
  await result.click()

  await expectFourTariffs(p)
  await p.getByRole('radio', { name: /Наличные/ }).click()
  const order = p.getByRole('button', { name: 'Заказать Эконом · Наличные' })
  await expect(order).toBeEnabled()
  await shoot(p, '04', 'passenger-choose-ride-4-253')
  await order.click()

  await expect(p.getByText('Подбираем ближайшего водителя')).toBeVisible(STEP)
  await shoot(p, '05', 'passenger-searching-5-268')

  await expect(d.getByText('Новый заказ')).toBeVisible(STEP)
  await expect(d.getByText('Оплата наличными')).toBeVisible()
  await expect(d.getByRole('timer', { name: /Осталось \d+ с/ })).toBeVisible()
  await addressesResolved(d)
  await shoot(d, '06', 'driver-offer-6-125')
  await d.getByRole('button', { name: 'Принять' }).click()

  await expect(d.getByRole('button', { name: 'Я на месте' })).toBeVisible(STEP)
  await expect(p.getByText('Водитель едет', { exact: true })).toBeVisible(STEP)
  await expect(p.getByText('DEMO001KZ')).toBeVisible()
  await shoot(d, '07a', 'driver-assigned-6-243')
  await shoot(p, '07b', 'passenger-driver-on-way-5-370')

  await d.getByRole('button', { name: 'Я на месте' }).click()
  await expect(d.getByRole('button', { name: 'Начать поездку' })).toBeVisible(STEP)
  await expect(p.getByText('Выходите — вас ждут')).toBeVisible(STEP)
  await shoot(d, '08a', 'driver-arrived-25-260')
  await shoot(p, '08b', 'passenger-arrived-24-351')

  await d.getByRole('button', { name: 'Начать поездку' }).click()
  await expect(d.getByRole('button', { name: 'Завершить поездку' })).toBeVisible(STEP)
  await expect(p.getByText('В пути', { exact: true })).toBeVisible(STEP)
  await shoot(d, '09a', 'driver-in-progress-25-359')
  await shoot(p, '09b', 'passenger-in-progress-24-451')

  await d.getByRole('button', { name: 'Завершить поездку' }).click()
  await expect(d.getByText('Получите оплату')).toBeVisible(STEP)
  await expect(p.getByText('Оплатите наличными')).toBeVisible(STEP)
  await shoot(d, '10a', 'driver-cash-13-442')
  await shoot(p, '10b', 'passenger-completed-cash-24-668')

  await d.getByRole('button', { name: 'Наличные получены' }).click()
  await expect(d.getByText('Получено наличными')).toBeVisible(STEP)
  await d.getByRole('radiogroup', { name: 'Оценка пассажира' }).getByRole('radio', { name: '5 из 5' }).click()
  await shoot(d, '11', 'driver-completed-kaspi-25-464')
  await d.getByRole('button', { name: 'Оценить и к новым заказам' }).click()
  await expect(d.getByText('Ищем заказы рядом')).toBeVisible(STEP)

  await expect(p.getByRole('heading', { name: 'Поездка завершена' })).toBeVisible(STEP)
  await expect(p.getByText('Оплачено', { exact: true })).toBeVisible()
  await p.getByRole('radio', { name: '5 из 5' }).click()
  await shoot(p, '12', 'passenger-completed-5-499')
  await p.getByRole('button', { name: 'Отправить оценку' }).click()
  await expect(p.getByText('Спасибо за оценку')).toBeVisible(STEP)
  await expect(p.getByRole('heading', { name: 'Куда едем?' })).toBeVisible()

  await driver.context.close()
  await passenger.context.close()
})

test('Kaspi ride: the link opens, paid at assignment, refunded on cancel', async ({ browser }) => {
  const driver = await phone(browser, DRIVER_POINT)
  const passenger = await phone(browser, PICKUP)
  const d = driver.page
  const p = passenger.page

  await driverOnline(d, null)
  await login(p, 'demo_passenger_1', /\/$/)

  await p.getByRole('button', { name: /Точка на карте/ }).click()
  await expect(p.getByRole('heading', { name: 'Куда едем?' })).toBeVisible()
  await p.mouse.move(195, 520)
  await p.mouse.down()
  await p.mouse.move(150, 300, { steps: 12 })
  await p.mouse.move(120, 160, { steps: 12 })
  await p.mouse.up()
  const done = p.getByRole('button', { name: 'Готово' })
  await expect(done).toBeEnabled(STEP)
  await shoot(p, '13', 'passenger-map-point-23-97')
  await done.click()

  await expectFourTariffs(p)
  await p.getByRole('radio', { name: /Kaspi/ }).click()
  const order = p.getByRole('button', { name: 'Заказать Эконом · Kaspi' })
  await expect(order).toBeEnabled()
  const [kaspi] = await Promise.all([passenger.context.waitForEvent('page'), order.click()])
  await kaspi.waitForURL(/^https:\/\/pay\.kaspi\.kz\//, { waitUntil: 'commit' })
  expect(new URL(kaspi.url()).host).toBe('pay.kaspi.kz')
  await kaspi.close()

  await expect(p.getByText('Подбираем ближайшего водителя')).toBeVisible(STEP)

  await expect(d.getByText('Новый заказ')).toBeVisible(STEP)
  await expect(d.getByText('Kaspi · спишется, когда вы примете заказ')).toBeVisible()
  await d.getByRole('button', { name: 'Принять' }).click()
  await expect(d.getByRole('button', { name: 'Я на месте' })).toBeVisible(STEP)

  await expect(p.getByRole('heading', { name: 'Водитель найден' })).toBeVisible(STEP)
  await expect(p.getByText(/списано через Kaspi в момент назначения/)).toBeVisible()
  await shoot(p, '14', 'passenger-driver-found-paid-23-191')

  await p.getByRole('button', { name: 'Где мой водитель?' }).click()
  await expect(p.getByText('Водитель едет', { exact: true })).toBeVisible()
  await p.getByRole('button', { name: 'Отменить' }).click()
  await expect(p.getByRole('heading', { name: 'Отменить поездку?' })).toBeVisible()
  await shoot(p, '15', 'passenger-cancel-confirm-24-555')
  await p.getByRole('button', { name: 'Да, отменить' }).click()

  await expect(p.getByRole('heading', { name: 'Поездка отменена' })).toBeVisible(STEP)
  await expect(p.getByText('Возвращено', { exact: true })).toBeVisible()
  await shoot(p, '16', 'passenger-cancelled-24-633')
  const route = p.getByRole('definition').filter({ hasText: '→' })
  const routeBox = await route.boundingBox()
  expect(routeBox && routeBox.x + routeBox.width, 'the route fits the receipt card').toBeLessThanOrEqual(VIEWPORT.width - 36)

  await expect(d.getByText('Пассажир отменил поездку')).toBeVisible(STEP)
  await shoot(d, '17', 'driver-cancelled-26-425')
  await d.getByRole('button', { name: 'Понятно' }).click()
  await expect(d.getByText('Ищем заказы рядом')).toBeVisible(STEP)

  await driver.context.close()
  await passenger.context.close()
})

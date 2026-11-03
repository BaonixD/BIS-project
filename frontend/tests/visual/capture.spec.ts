import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { test, type Page } from '@playwright/test'

const OUT = path.join(import.meta.dirname, 'screenshots')
mkdirSync(OUT, { recursive: true })

const shot = (name: string) => path.join(OUT, `${name}.png`)

/** No backend: anonymous session, Google enabled (to show the button), GIS script blocked. */
async function mockBackend(page: Page) {
  await page.route('**/api/v1/auth/session', (route) =>
    route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ error: { code: 'not_authenticated', message: 'No session', details: {} } }),
    }),
  )
  await page.route('**/api/v1/auth/providers', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify({ google_client_id: 'visual-test' }) }),
  )
  await page.route('https://accounts.google.com/**', (route) => route.abort())
  await page.route('https://tiles.openfreemap.org/**', (route) => route.abort())
}

async function settle(page: Page) {
  await page.evaluate('document.fonts.ready')
  await page.waitForTimeout(600)
}

for (const width of [390, 1440]) {
  test.describe(`${width}px`, () => {
    test.use({ viewport: { width, height: width === 390 ? 844 : 900 } })

    test('auth screens', async ({ page }) => {
      await mockBackend(page)
      await page.goto('/login')
      await page.getByRole('button', { name: /Продолжить с Google/ }).waitFor()
      await page.locator('input[name="username"]').focus()
      await settle(page)
      await page.screenshot({ path: shot(`login-${width}`) })
      await page.goto('/register')
      await settle(page)
      await page.screenshot({ path: shot(`register-${width}`) })
    })

    test('kit page', async ({ page }) => {
      await mockBackend(page)
      await page.goto('/dev/kit')
      await page.getByRole('heading', { name: 'UI kit' }).waitFor()
      await settle(page)
      await page.screenshot({ path: shot(`kit-${width}`), fullPage: true })
      if (width !== 1440) return
      for (const frame of await page.locator('[data-figma]').all()) {
        const id = (await frame.getAttribute('data-figma'))?.replace(/[^0-9a-z]+/gi, '-')
        await frame.screenshot({ path: shot(`kit-${id}`) })
      }
    })
  })
}

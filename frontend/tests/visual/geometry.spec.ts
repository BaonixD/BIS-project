import { expect, test, type Page } from '@playwright/test'

/** The mockup's iPhone status bar (Figma StatusBar 3:106) is not part of the web page. */
const STATUS_BAR = 47

test.use({ viewport: { width: 390, height: 844 } })

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
}

/** Top-level blocks of <main>: [y in the Figma frame, height]. */
async function blocks(page: Page) {
  return page.locator('main > *').evaluateAll((nodes, offset) =>
    nodes.map((node) => {
      const rect = node.getBoundingClientRect()
      const isBackLink = node.tagName === 'A' && node.getAttribute('aria-label')
      return isBackLink ? [rect.y + 10 + offset, rect.height - 20] : [rect.y + offset, rect.height]
    }),
  STATUS_BAR)
}

test('login matches Figma 4:2 (Content 4:13)', async ({ page }) => {
  await mockBackend(page)
  await page.goto('/login')
  await page.getByRole('button', { name: /Продолжить с Google/ }).waitFor()
  // Logo, Heading, Form + Button (one <form>), Divider, GoogleButton, footer text.
  expect(await blocks(page)).toEqual([
    [96, 40],
    [160, 68],
    [252, 204],
    [480, 18],
    [522, 56],
    [602, 20],
  ])
})

test('register matches Figma 4:43 (Content 4:54)', async ({ page }) => {
  await mockBackend(page)
  await page.goto('/register')
  await page.getByRole('heading', { name: 'Создать аккаунт' }).waitFor()
  // Back arrow, Heading, RolePicker, Form + Button, note.
  expect(await blocks(page)).toEqual([
    [64, 24],
    [112, 68],
    [204, 122],
    [350, 204],
    [578, 36],
  ])
})

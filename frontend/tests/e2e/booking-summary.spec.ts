import { expect, test } from '@playwright/test'
import { DEMO_PASSWORD } from './env.ts'

test('arrival forecast is on the map and all tariffs can be scrolled and selected', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/login')
  await page.locator('input[name="username"]').fill('demo_passenger_1')
  await page.locator('input[name="password"]').fill(DEMO_PASSWORD)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await page.waitForURL('/')
  await page.getByRole('button', { name: /Esentai Mall/ }).click()
  const summary = page.getByRole('region', { name: 'Прогноз прибытия' })
  await expect(summary).toBeVisible()
  await expect(summary).toContainText(/Прибытие ≈\d{2}:\d{2}/)
  await expect(summary).toContainText(/\d+ мин/)
  await expect(summary).toContainText(/\d.*км/)
  await expect(summary).toContainText('Если выехать сейчас · без пробок')
  const sheet = page.locator('[data-slot="bottom-sheet"]')
  await expect(sheet.getByRole('region', { name: 'Прогноз прибытия' })).toHaveCount(0)
  await expect(sheet.getByText('Время в пути')).toHaveCount(0)
  const label = page.locator('.bis-arrival-label')
  await expect
    .poll(async () => {
      const box = await label.boundingBox()
      const panel = await sheet.boundingBox()
      return Boolean(
        box && panel && box.x >= panel.x + panel.width && box.x + box.width <= 1440 && box.y >= 64,
      )
    })
    .toBe(true)
  const strip = page.getByRole('radiogroup', { name: 'Тариф' })
  await expect(strip).toBeVisible()
  await expect(page.getByRole('button', { name: 'Следующие тарифы' })).toHaveCount(0)
  await strip.hover()
  await page.mouse.wheel(600, 0)
  await expect.poll(() => strip.evaluate((node) => node.scrollLeft)).toBeGreaterThan(0)
  const business = strip.getByRole('radio', { name: /Бизнес/ })
  await business.click()
  await expect(business).toBeChecked()
  await expect(page.getByRole('button', { name: 'Заказать Бизнес · Наличные' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('desktop-booking.png') })
  await business.press('Home')
  await expect(strip.getByRole('radio', { name: /Эконом/ })).toBeChecked()
  await expect.poll(() => strip.evaluate((node) => node.scrollLeft)).toBeLessThan(5)
  await strip.hover()
  await page.mouse.wheel(600, 0)
  await expect.poll(() => strip.evaluate((node) => node.scrollLeft)).toBeGreaterThan(0)
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(summary).toBeVisible()
  await expect
    .poll(async () => {
      const box = await label.boundingBox()
      const panel = await sheet.boundingBox()
      return Boolean(
        box &&
        panel &&
        box.x >= 0 &&
        box.x + box.width <= 390 &&
        box.y >= 0 &&
        box.y + box.height < panel.y,
      )
    })
    .toBe(true)
  await page.screenshot({ path: testInfo.outputPath('mobile-booking.png') })
})

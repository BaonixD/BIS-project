import { execFileSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { test, expect, type Page } from '@playwright/test'
import { ADMIN_PASSWORD, BACKEND_DIR, DB_FILE, DEMO_PASSWORD, FRONTEND_PORT } from './env.ts'

async function login(page: Page, username: string, password: string) {
  await page.goto('/login')
  await page.locator('input[name="username"]').fill(username)
  await page.locator('input[name="password"]').fill(password)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).not.toHaveURL(/\/login$/)
}

test('documents are reviewed by admin and support replies reach the driver', async ({
  browser,
}, testInfo) => {
  const directory = path.dirname(DB_FILE)
  mkdirSync(directory, { recursive: true })
  const filename = path.join(directory, 'synthetic-document.pdf')
  execFileSync(
    'uv',
    [
      'run',
      'python',
      '-c',
      'from pypdf import PdfWriter; import sys; w=PdfWriter(); w.add_blank_page(width=300,height=400); w.add_metadata({"/Title":"DEMO - no personal data"}); w.write(sys.argv[1])',
      filename,
    ],
    { cwd: BACKEND_DIR, stdio: 'pipe' },
  )
  const driverContext = await browser.newContext({
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    viewport: { width: 390, height: 844 },
  })
  const adminContext = await browser.newContext({
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    viewport: { width: 1440, height: 1000 },
  })
  const driver = await driverContext.newPage()
  const admin = await adminContext.newPage()
  try {
    await driver.goto('/login')
    const registered = await driver.request.post('/api/v1/auth/register', {
      data: { username: 'documents_driver', password: DEMO_PASSWORD, role: 'driver' },
    })
    expect(registered.ok()).toBeTruthy()
    const user = await registered.json()
    await login(driver, 'documents_driver', DEMO_PASSWORD)
    const session = await (await driver.request.get('/api/v1/auth/session')).json()
    const profile = await driver.request.patch('/api/v1/drivers/me', {
      headers: { 'X-CSRF-Token': session.csrf_token },
      data: {
        full_name: 'Demo Documents Driver',
        phone: '+77011234567',
        license_number: 'KZ999999',
        vehicle: {
          make: 'Toyota',
          model: 'Camry',
          color: 'white',
          plate_number: '999DOC02',
          year: 2020,
        },
      },
    })
    expect(profile.ok()).toBeTruthy()
    await driver.goto('/driver/documents')
    await driver.getByLabel('Загрузить удостоверение', { exact: true }).setInputFiles(filename)
    await expect(driver.getByText('synthetic-document.pdf', { exact: true })).toHaveCount(1)
    await driver.getByLabel('Загрузить права', { exact: true }).setInputFiles(filename)
    await expect(driver.getByRole('button', { name: 'Отправить на проверку' })).toBeEnabled()
    await driver.getByRole('button', { name: 'Отправить на проверку' }).click()
    await expect(driver.getByText('На проверке', { exact: true })).toBeVisible()
    await driver.screenshot({ path: testInfo.outputPath('documents-driver.png'), fullPage: true })
    await login(admin, 'admin', ADMIN_PASSWORD)
    await admin.goto(`/admin/drivers/${user.id}`)
    await admin.screenshot({ path: testInfo.outputPath('documents-admin.png'), fullPage: true })
    await admin.getByRole('button', { name: 'Посмотреть', exact: true }).first().click()
    const pdf = admin.getByRole('dialog', { name: 'synthetic-document.pdf' })
    await expect(pdf.getByRole('link', { name: 'Скачать PDF' })).toBeVisible()
    await expect(pdf.locator('canvas')).toHaveAttribute('width', '300')
    await pdf.getByRole('button', { name: 'Закрыть' }).click()
    await admin.getByRole('button', { name: 'Вернуть на исправление' }).click()
    const review = admin.getByRole('dialog')
    await review.getByRole('textbox', { name: 'Причина' }).fill('Нужна чёткая копия')
    await review.getByRole('button', { name: 'Отправить' }).click()
    await expect(review).not.toBeVisible()
    await driver.reload()
    await expect(driver.getByText('Нужна чёткая копия')).toBeVisible()
    await driver.getByRole('button', { name: 'Исправить документы' }).click()
    await expect(driver.getByText('Черновик', { exact: true })).toBeVisible()
    await driver.getByLabel('Загрузить удостоверение', { exact: true }).setInputFiles(filename)
    await expect(driver.getByRole('button', { name: 'Отправить на проверку' })).toBeEnabled()
    await driver.getByRole('button', { name: 'Отправить на проверку' }).click()
    await expect(driver.getByText('На проверке', { exact: true })).toBeVisible()
    await admin.reload()
    await admin.getByRole('button', { name: 'Одобрить водителя' }).click()
    const category = admin.getByRole('dialog', { name: 'Класс машины' })
    await category.getByRole('radio', { name: /Бизнес/ }).click()
    await category.getByRole('button', { name: 'Одобрить', exact: true }).click()
    await expect(admin.getByText('Документы проверены', { exact: true })).toBeVisible()
    await driver.goto('/driver')
    await driver.getByRole('button', { name: 'Выйти на линию', exact: true }).click()
    const shift = driver.getByRole('dialog', { name: 'Тарифы смены' })
    await expect(shift.getByRole('checkbox')).toHaveCount(4)
    await shift.getByRole('button', { name: 'Выйти на линию', exact: true }).click()
    await expect(driver.getByText('Ищем заказы рядом', { exact: true })).toBeVisible()
    await driver.goto('/driver/support')
    await driver.getByRole('button', { name: 'Написать', exact: true }).click()
    const contact = driver.getByRole('dialog', { name: 'Новое обращение' })
    await contact.getByRole('textbox', { name: 'Тема' }).fill('Вопрос по документам')
    await contact.getByRole('textbox', { name: 'Сообщение' }).fill('Как обновить документы?')
    await contact.getByRole('button', { name: 'Отправить' }).click()
    await expect(driver).toHaveURL(/\/driver\/support\//)
    await admin.goto('/admin/support')
    await admin.getByRole('link').filter({ hasText: 'Вопрос по документам' }).click()
    await expect(admin.getByText('Как обновить документы?', { exact: true })).toBeVisible()
    await admin
      .getByRole('textbox', { name: 'Сообщение' })
      .fill('Откройте раздел документов в профиле.')
    await admin.getByRole('button', { name: 'Отправить', exact: true }).click()
    await driver.bringToFront()
    await expect(
      driver.getByText('Откройте раздел документов в профиле.', { exact: true }),
    ).toBeVisible()
    await admin.bringToFront()
    await admin.getByRole('button', { name: 'Решить вопрос', exact: true }).click()
    await driver.bringToFront()
    await expect(driver.getByText('Решено', { exact: true })).toBeVisible()
    await driver.getByRole('textbox', { name: 'Сообщение' }).fill('Спасибо, а где кнопка?')
    await driver.getByRole('button', { name: 'Отправить', exact: true }).click()
    await admin.bringToFront()
    await expect(admin.getByText('Открыто', { exact: true })).toBeVisible()
    await driver.screenshot({ path: testInfo.outputPath('support-driver.png'), fullPage: true })
  } finally {
    await driverContext.close()
    await adminContext.close()
  }
})

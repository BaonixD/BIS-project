import { defineConfig } from '@playwright/test'
import { BACKEND_DIR, BACKEND_PORT, DATABASE_URL, DB_FILES, FRONTEND_PORT } from './env.ts'

const backendEnv = { DATABASE_URL, SESSION_COOKIE_SECURE: 'false' }
const quote = (value: string) => `'${value.replaceAll("'", "'\\''")}'`

/**
 * A full ride in a real browser on the real backend: real openrouteservice routes (the key from the
 * backend's `.env`), real Nominatim and map tiles. One uvicorn, one Vite, one worker.
 * Playwright starts the web servers before `globalSetup`: the backend command removes the previous
 * database first, so the server never holds a connection to a stale file; `globalSetup` then
 * migrates and seeds the new one.
 */
export default defineConfig({
  testDir: '.',
  outputDir: './.results',
  globalSetup: './global-setup.ts',
  workers: 1,
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  timeout: 6 * 60_000,
  expect: { timeout: 20_000 },
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    channel: 'chrome',
    deviceScaleFactor: 1,
    locale: 'ru-RU',
    timezoneId: 'Asia/Almaty',
    trace: 'retain-on-failure',
    actionTimeout: 30_000,
  },
  webServer: [
    {
      command: `rm -f ${DB_FILES.map(quote).join(' ')} && exec uv run uvicorn --factory taxi_service.main:create_app --port ${BACKEND_PORT}`,
      cwd: BACKEND_DIR,
      env: backendEnv,
      url: `http://127.0.0.1:${BACKEND_PORT}/health/live`,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: 'ignore',
      stderr: 'pipe',
    },
    {
      command: 'npm run dev',
      cwd: '../..',
      url: `http://localhost:${FRONTEND_PORT}/login`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})

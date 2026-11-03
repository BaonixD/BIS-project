import { defineConfig } from '@playwright/test'

const PORT = Number(process.env.VISUAL_PORT ?? 5199)

/** Screenshots for comparing the app with the Figma frames; not part of `npm test`. */
export default defineConfig({
  testDir: '.',
  outputDir: './.results',
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    channel: 'chrome',
    deviceScaleFactor: 1,
  },
  webServer: {
    command: `npx vite --port ${PORT} --strictPort`,
    cwd: '../..',
    url: `http://localhost:${PORT}/login`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
})

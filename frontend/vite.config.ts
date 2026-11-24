/// <reference types="vitest/config" />
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { readFileSync, writeFileSync } from 'node:fs'
import { defineConfig, type Plugin } from 'vite'

/**
 * Offline support for public/sw.js: lists every built file in precache.json and stamps the
 * worker with a build id, so each release installs a new worker and a fresh cache.
 */
function precacheManifest(): Plugin {
  let outDir = 'dist'
  let files: string[] = []
  return {
    name: 'tulpar-precache',
    apply: 'build',
    configResolved(config) {
      outDir = path.resolve(config.root, config.build.outDir)
    },
    generateBundle(_options, bundle) {
      files = Object.keys(bundle)
        .filter((file) => /\.(js|css|woff2?|png|svg|jpe?g|webp)$/.test(file))
        .map((file) => `/${file}`)
      this.emitFile({ type: 'asset', fileName: 'precache.json', source: JSON.stringify(files) })
    },
    closeBundle() {
      const worker = path.join(outDir, 'sw.js')
      const build = Date.now().toString(36)
      writeFileSync(worker, readFileSync(worker, 'utf8').replace('__BUILD_ID__', build))
    },
  }
}

const BACKEND_URL = process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss(), precacheManifest()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: BACKEND_URL },
      '/health': { target: BACKEND_URL },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['src/test/setup.ts'],
    css: false,
    restoreMocks: true,
  },
})

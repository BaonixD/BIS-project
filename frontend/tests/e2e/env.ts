import { execFileSync } from 'node:child_process'
import path from 'node:path'

/**
 * The real backend runs from the main checkout (the parent of the shared `.git`, also from a worktree):
 * its current API and its local `.env` with ROUTING_API_KEY, ROUTING_BASE_URL and KASPI_PAYMENT_URL.
 */
function mainCheckout(): string {
  const gitDir = execFileSync('git', ['rev-parse', '--path-format=absolute', '--git-common-dir'], {
    cwd: import.meta.dirname,
    encoding: 'utf8',
  })
  return path.dirname(gitDir.trim())
}

export const BACKEND_DIR = process.env.E2E_BACKEND_DIR ?? mainCheckout()
export const DB_FILE =
  process.env.E2E_DB_FILE ??
  '/private/tmp/claude-501/-Users-baonix-BIS-project/1ae3258e-aff6-400e-858d-b2e0c04ac3d6/scratchpad/e2e.db'
export const DATABASE_URL = `sqlite+aiosqlite:///${DB_FILE}`
export const BACKEND_PORT = 8000
export const FRONTEND_PORT = 5173

/** Accounts of a throwaway database. */
export const DEMO_PASSWORD = 'e2e-demo-password'
export const ADMIN_PASSWORD = 'e2e-admin-password'

export const DB_FILES = ['', '-wal', '-shm', '-journal'].map((suffix) => `${DB_FILE}${suffix}`)

import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { mkdirSync, realpathSync } from 'node:fs'
import { tmpdir } from 'node:os'

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
export const DB_FILE = process.env.E2E_DB_FILE ?? '/private/tmp/bis-taxi-e2e/state/e2e.db'
mkdirSync(path.dirname(DB_FILE), { recursive: true })
if (
  !realpathSync(path.dirname(DB_FILE)).startsWith(
    realpathSync(tmpdir()).replace(/\/$/, '') + '/',
  ) &&
  !realpathSync(path.dirname(DB_FILE)).startsWith('/private/tmp/')
)
  throw new Error('E2E database must stay in a temporary directory')
export const DOCUMENT_STORAGE_DIR = path.join(path.dirname(DB_FILE), 'private-documents')
export const DATABASE_URL = `sqlite+aiosqlite:///${DB_FILE}`
export const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT ?? 8100)
export const FRONTEND_PORT = Number(process.env.E2E_FRONTEND_PORT ?? 5190)

/** Accounts of a throwaway database. */
export const DEMO_PASSWORD = 'e2e-demo-password'
export const ADMIN_PASSWORD = 'e2e-admin-password'

export const DB_FILES = ['', '-wal', '-shm', '-journal'].map((suffix) => `${DB_FILE}${suffix}`)

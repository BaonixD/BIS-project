import { execFileSync } from 'node:child_process'
import { rmSync } from 'node:fs'
import { ADMIN_PASSWORD, BACKEND_DIR, DATABASE_URL, DB_FILES, DEMO_PASSWORD } from './env.ts'

function backend(args: string[], extra: Record<string, string> = {}) {
  execFileSync('uv', ['run', ...args], {
    cwd: BACKEND_DIR,
    env: { ...process.env, DATABASE_URL, ...extra },
    stdio: ['ignore', 'inherit', 'inherit'],
  })
}

/** A fresh SQLite database: migrations, an admin and the demo seed (drivers online near the demo pickup). */
export default function globalSetup() {
  for (const file of DB_FILES) rmSync(file, { force: true })
  backend(['alembic', 'upgrade', 'head'])
  backend(['python', 'scripts/create_admin.py', '--username', 'admin'], { ADMIN_PASSWORD })
  backend(['python', 'scripts/seed.py'], { DEMO_PASSWORD })
}

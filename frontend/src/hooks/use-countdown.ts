import { useEffect, useState } from 'react'

/** Current time, re-rendering every `intervalMs` while `active`. */
export function useNow(intervalMs = 1000, active = true): number {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs)
    return () => window.clearInterval(timer)
  }, [intervalMs, active])

  return now
}

/** Seconds until the server-side `expires_at`; 0 once expired. */
export function useCountdown(expiresAt: string | null | undefined): number {
  const now = useNow(1000, Boolean(expiresAt))
  if (!expiresAt) return 0
  return Math.max(0, Math.ceil((Date.parse(expiresAt) - now) / 1000))
}

import { useSyncExternalStore } from 'react'

/** Chrome's install event; not in the DOM typings. */
interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

interface PwaState {
  /** A new build is installed and waits for «Обновить». */
  updateReady: boolean
  /** Android/desktop Chrome offered installation. */
  canInstall: boolean
  online: boolean
}

const listeners = new Set<() => void>()
let state: PwaState = {
  updateReady: false,
  canInstall: false,
  online: typeof navigator === 'undefined' ? true : navigator.onLine,
}
let waiting: ServiceWorker | null = null
let installPrompt: InstallPromptEvent | null = null
/** Set by «Обновить»: the first install also changes the controller and must not reload. */
let switching = false

function set(next: Partial<PwaState>): void {
  state = { ...state, ...next }
  listeners.forEach((listener) => listener())
}

export function usePwa(): PwaState {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => state,
    () => state,
  )
}

/** True when opened from the home screen (no browser address bar). */
export function isStandalone(): boolean {
  if (typeof window === 'undefined') return false
  const iosStandalone = (navigator as Navigator & { standalone?: boolean }).standalone === true
  return iosStandalone || window.matchMedia?.('(display-mode: standalone)').matches === true
}

/** iPhone or iPad Safari, where installing means «Поделиться → На экран „Домой“». */
export function isIosSafari(): boolean {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent
  const ios = /iPad|iPhone|iPod/.test(ua) || (ua.includes('Macintosh') && navigator.maxTouchPoints > 1)
  return ios && /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua)
}

export async function promptInstall(): Promise<void> {
  if (!installPrompt) return
  await installPrompt.prompt()
  await installPrompt.userChoice
  installPrompt = null
  set({ canInstall: false })
}

/** Switch to the waiting build; the page reloads once the new worker takes over. */
export function applyUpdate(): void {
  if (!waiting) return
  switching = true
  waiting.postMessage('SKIP_WAITING')
}

function watch(registration: ServiceWorkerRegistration): void {
  const remember = (worker: ServiceWorker | null) => {
    // Only an update: the very first install has no controller yet and needs no reload.
    if (worker && navigator.serviceWorker.controller) {
      waiting = worker
      set({ updateReady: true })
    }
  }
  remember(registration.waiting)
  registration.addEventListener('updatefound', () => {
    const installing = registration.installing
    installing?.addEventListener('statechange', () => {
      if (installing.state === 'installed') remember(installing)
    })
  })
}

/** Called once from main.tsx. */
export function setupPwa(): void {
  if (typeof window === 'undefined') return
  window.addEventListener('online', () => set({ online: true }))
  window.addEventListener('offline', () => set({ online: false }))
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault()
    installPrompt = event as InstallPromptEvent
    set({ canInstall: true })
  })
  window.addEventListener('appinstalled', () => {
    installPrompt = null
    set({ canInstall: false })
  })
  // Development keeps Vite's hot reload; the worker runs only in the production build.
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (!switching) return
    switching = false
    window.location.reload()
  })
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js')
      .then((registration) => {
        watch(registration)
        const check = () => void registration.update().catch(() => undefined)
        window.setInterval(check, 30 * 60_000)
        document.addEventListener('visibilitychange', () => {
          if (!document.hidden) check()
        })
      })
      .catch(() => undefined)
  })
}

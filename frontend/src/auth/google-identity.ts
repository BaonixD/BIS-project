/** Minimal typing of Google Identity Services (https://developers.google.com/identity/gsi/web/reference/js-reference). */
interface CredentialResponse {
  credential: string
}

interface GoogleIdentity {
  initialize(config: {
    client_id: string
    callback: (response: CredentialResponse) => void
    ux_mode?: 'popup' | 'redirect'
    context?: 'signin' | 'signup' | 'use'
  }): void
  renderButton(parent: HTMLElement, options: Record<string, string | number>): void
  prompt(): void
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleIdentity } }
  }
}

const SCRIPT_URL = 'https://accounts.google.com/gsi/client'
let loading: Promise<GoogleIdentity> | null = null

export function loadGoogleIdentity(): Promise<GoogleIdentity> {
  if (window.google?.accounts.id) return Promise.resolve(window.google.accounts.id)
  loading ??= new Promise<GoogleIdentity>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = SCRIPT_URL
    script.async = true
    script.onload = () =>
      window.google?.accounts.id ? resolve(window.google.accounts.id) : reject(new Error('GIS unavailable'))
    script.onerror = () => {
      loading = null
      reject(new Error('Failed to load Google Identity Services'))
    }
    document.head.append(script)
  })
  return loading
}

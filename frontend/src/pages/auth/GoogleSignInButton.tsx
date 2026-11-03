import { useEffect, useRef } from 'react'
import googleIcon from '@/assets/icons/google.svg'
import { loadGoogleIdentity } from '@/auth/google-identity'
import { cn } from '@/lib/utils'

const GIS_MAX_WIDTH = 400

/**
 * Figma «GoogleButton» 12:538. Google Identity Services only issues an ID token from its own button,
 * so the official button is rendered transparently over the Figma one and receives the click;
 * the visible button falls back to the One Tap prompt.
 */
export function GoogleSignInButton({
  clientId,
  onCredential,
  disabled,
}: {
  clientId: string
  onCredential: (credential: string) => void
  disabled?: boolean
}) {
  const overlay = useRef<HTMLDivElement>(null)
  const callback = useRef(onCredential)

  useEffect(() => {
    callback.current = onCredential
  }, [onCredential])

  useEffect(() => {
    let cancelled = false
    loadGoogleIdentity()
      .then((identity) => {
        const target = overlay.current
        if (cancelled || !target) return
        identity.initialize({
          client_id: clientId,
          callback: (response) => callback.current(response.credential),
          ux_mode: 'popup',
          context: 'signin',
        })
        target.replaceChildren()
        identity.renderButton(target, {
          type: 'standard',
          theme: 'outline',
          size: 'large',
          text: 'continue_with',
          locale: 'ru',
          width: Math.min(GIS_MAX_WIDTH, target.offsetWidth),
        })
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [clientId])

  return (
    <div className="relative w-full">
      <button
        type="button"
        disabled={disabled}
        onClick={() => window.google?.accounts.id.prompt()}
        className={cn(
          'flex h-14 w-full items-center justify-center gap-2.5 overflow-hidden rounded-md border-[1.5px] border-solid border-border-default bg-bg-canvas',
          'text-body-medium text-text-primary outline-none transition-opacity active:opacity-70 focus-visible:ring-2 focus-visible:ring-bg-inverse disabled:opacity-40',
        )}
      >
        <img src={googleIcon} alt="" className="size-6" />
        Продолжить с Google
      </button>
      <div
        ref={overlay}
        className={cn('absolute inset-0 flex items-center justify-center overflow-hidden opacity-[0.01]', disabled && 'hidden')}
      />
    </div>
  )
}

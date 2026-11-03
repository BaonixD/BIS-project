import { Link, useLocation } from 'react-router'
import type { UserRole } from '@/api'
import { ROLE_HOME } from '@/auth/role-home'
import { cn } from '@/lib/utils'
import { isNavItemActive, NAV_ITEMS, PROFILE_PATH } from './nav-items'

function Account({ displayName }: { displayName: string }) {
  return (
    <>
      <span
        aria-hidden
        className="flex size-8 shrink-0 items-center justify-center rounded-full bg-bg-canvas text-label text-text-primary"
      >
        {displayName.charAt(0).toUpperCase()}
      </span>
      <span className="text-callout whitespace-nowrap text-text-inverse">{displayName}</span>
    </>
  )
}

/** Figma Desktop 7:2 «TopBar»: 64px black bar with the brand, role links and the account (≥1024px only). */
export function TopBar({
  role,
  displayName,
  pathname: pathnameOverride,
  preview = false,
}: {
  role: UserRole
  displayName: string
  pathname?: string
  /** Kit preview: render in the flow at every width. */
  preview?: boolean
}) {
  const location = useLocation()
  const pathname = pathnameOverride ?? location.pathname
  const profile = PROFILE_PATH[role]
  return (
    <header
      className={cn(
        'h-(--top-bar-height) items-center gap-8 overflow-hidden bg-bg-inverse px-8',
        preview ? 'flex w-full' : 'fixed inset-x-0 top-0 z-40 hidden lg:flex',
      )}
    >
      <Link to={ROLE_HOME[role]} className="text-headline whitespace-nowrap text-text-inverse">
        BIS Taxi
      </Link>
      <nav aria-label="Разделы" className="flex min-w-0 flex-1 items-center gap-6">
        {NAV_ITEMS[role].map((item) => {
          const active = isNavItemActive(item, pathname)
          return (
            <Link
              key={item.to}
              to={item.to}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'text-callout whitespace-nowrap text-text-inverse transition-opacity duration-150 hover:opacity-100',
                !active && 'opacity-60',
              )}
            >
              {item.label}
            </Link>
          )
        })}
      </nav>
      {profile ? (
        <Link to={profile} className="flex shrink-0 items-center gap-2.5">
          <Account displayName={displayName} />
        </Link>
      ) : (
        <div className="flex shrink-0 items-center gap-2.5">
          <Account displayName={displayName} />
        </div>
      )}
    </header>
  )
}

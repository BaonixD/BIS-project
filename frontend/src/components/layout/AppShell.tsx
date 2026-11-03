import { Suspense } from 'react'
import { Outlet, useLocation } from 'react-router'
import { cn } from '@/lib/utils'
import { useSession } from '@/auth/use-session'
import { FullScreenLoader } from '@/components/common/FullScreenLoader'
import { useMyProfile } from '@/hooks/use-profile'
import { BottomNav } from './BottomNav'
import { useBottomNavHidden } from './nav-visibility'
import { TopBar } from './TopBar'

/**
 * Mobile: content above the floating bottom nav; map sheets sit 12px under the nav pill (`--sheet-offset`).
 * ≥1024px: the black top bar (Desktop 7:2) replaces the bottom nav.
 */
export function AppShell() {
  const { user } = useSession()
  const { pathname } = useLocation()
  const navHidden = useBottomNavHidden()
  const profile = useMyProfile(Boolean(user))
  const displayName = profile.data?.display_name || user?.username || ''
  return (
    <div
      className={cn(
        "min-h-dvh bg-bg-canvas text-text-primary lg:[--sheet-offset:0px]",
        navHidden ? "[--sheet-offset:0px]" : "[--sheet-offset:calc(var(--nav-height)-12px)]",
      )}
    >
      {user && <TopBar role={user.role} displayName={displayName} />}
      <main className={cn("lg:pt-(--top-bar-height) lg:pb-0", !navHidden && "pb-(--nav-height)")}>
        <div key={pathname} className="animate-page-in">
          <Suspense fallback={<FullScreenLoader />}>
            <Outlet />
          </Suspense>
        </div>
      </main>
      {user && !navHidden && <BottomNav role={user.role} />}
    </div>
  )
}

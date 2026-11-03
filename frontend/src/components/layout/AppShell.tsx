import { Suspense } from 'react'
import { Outlet } from 'react-router'
import { useSession } from '@/auth/use-session'
import { FullScreenLoader } from '@/components/common/FullScreenLoader'
import { BottomNav } from './BottomNav'
import { TopBar } from './TopBar'

/**
 * Mobile: content above the floating bottom nav; map sheets sit 12px under the nav pill (`--sheet-offset`).
 * ≥1024px: the black top bar (Desktop 7:2) replaces the bottom nav.
 */
export function AppShell() {
  const { user } = useSession()
  return (
    <div className="min-h-dvh bg-bg-canvas text-text-primary [--sheet-offset:calc(var(--nav-height)-12px)] lg:[--sheet-offset:0px]">
      {user && <TopBar role={user.role} displayName={user.username} />}
      <main className="pb-(--nav-height) lg:pt-(--top-bar-height) lg:pb-0">
        <Suspense fallback={<FullScreenLoader />}>
          <Outlet />
        </Suspense>
      </main>
      {user && <BottomNav role={user.role} />}
    </div>
  )
}

import { Outlet } from 'react-router'
import { useSession } from '@/auth/use-session'
import { BottomNav } from './BottomNav'
import { NAV_ITEMS } from './nav-items'

/** Content stays clear of the fixed bottom nav (mobile) or the side nav (≥ 1024px). */
export function AppShell() {
  const { user } = useSession()
  return (
    <div className="min-h-dvh bg-background text-foreground">
      <main className="pb-[calc(var(--bottom-nav-height)+env(safe-area-inset-bottom))] lg:pb-0 lg:pl-(--side-nav-width)">
        <Outlet />
      </main>
      {user && <BottomNav items={NAV_ITEMS[user.role]} />}
    </div>
  )
}

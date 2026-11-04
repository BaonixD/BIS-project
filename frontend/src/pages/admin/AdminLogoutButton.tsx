import { LogOut } from 'lucide-react'
import { useSession } from '@/auth/use-session'

/** The admin has no profile page: on mobile logout sits in the page header (desktop: the top bar). */
export function AdminLogoutButton() {
  const { logout } = useSession()
  return (
    <button
      type="button"
      aria-label="Выйти"
      disabled={logout.isPending}
      onClick={() => logout.mutate()}
      className="flex size-11 shrink-0 items-center justify-center rounded-full bg-bg-canvas text-accent-danger outline-none transition-opacity active:opacity-60 focus-visible:ring-2 focus-visible:ring-bg-inverse disabled:opacity-40 lg:hidden"
    >
      <LogOut className="size-5" strokeWidth={2} aria-hidden />
    </button>
  )
}

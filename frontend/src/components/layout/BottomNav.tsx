import { NavLink } from 'react-router'
import { cn } from '@/lib/utils'
import type { NavItem } from './nav-items'

export function BottomNav({ items }: { items: NavItem[] }) {
  return (
    <nav
      aria-label="Основная навигация"
      className={cn(
        'fixed inset-x-0 bottom-0 z-50 border-t bg-background/95 backdrop-blur',
        'pb-[env(safe-area-inset-bottom)]',
        'lg:inset-y-0 lg:right-auto lg:w-(--side-nav-width) lg:border-t-0 lg:border-r lg:pb-0',
      )}
    >
      <ul className="flex h-(--bottom-nav-height) items-stretch lg:h-auto lg:flex-col lg:gap-1 lg:p-3">
        {items.map(({ to, label, icon: Icon, end }) => (
          <li key={to} className="flex-1 lg:flex-none">
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'flex h-full flex-col items-center justify-center gap-1 text-xs font-medium text-muted-foreground transition-colors',
                  'lg:flex-row lg:justify-start lg:gap-3 lg:rounded-md lg:px-3 lg:py-2 lg:text-sm',
                  isActive && 'text-foreground lg:bg-accent',
                )
              }
            >
              <Icon className="size-5" aria-hidden />
              <span>{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

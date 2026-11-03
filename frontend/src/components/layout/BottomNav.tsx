import { Link, useLocation } from 'react-router'
import { motion } from 'motion/react'
import type { UserRole } from '@/api'
import { cn } from '@/lib/utils'
import { isNavItemActive, NAV_ITEMS } from './nav-items'

/**
 * Figma «BottomNav» 3:85: a floating white pill (16px inset, radius 28, 1px border, Elevation/Card);
 * the active item sits on a light-grey radius-20 capsule that glides between items.
 * Hidden at ≥1024px, where the black TopBar takes over.
 */
export function BottomNav({
  role,
  pathname: pathnameOverride,
  preview = false,
}: {
  role: UserRole
  /** Kit preview: highlight this path instead of the current one. */
  pathname?: string
  /** Kit preview: render in the flow at every width. */
  preview?: boolean
}) {
  const location = useLocation()
  const pathname = pathnameOverride ?? location.pathname
  return (
    <nav
      aria-label={preview ? `Навигация: ${role}` : 'Основная навигация'}
      className={cn(
        'px-4 pt-2 pb-(--nav-bottom-gap)',
        preview ? 'relative w-full' : 'pointer-events-none fixed inset-x-0 bottom-0 z-40 lg:hidden',
      )}
    >
      <ul className="pointer-events-auto flex items-center gap-1 overflow-hidden rounded-[28px] border border-solid border-border-default bg-bg-canvas p-1.5 shadow-card">
        {NAV_ITEMS[role].map((item) => {
          const active = isNavItemActive(item, pathname)
          const Icon = item.icon
          return (
            <li key={item.to} className="flex min-w-0 flex-1">
              <Link
                to={item.to}
                aria-current={active ? 'page' : undefined}
                className="relative flex min-w-0 flex-1 flex-col items-center justify-center gap-[3px] rounded-[20px] px-3 py-1.5 outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
              >
                {active && (
                  <motion.span
                    layoutId={preview ? `nav-active-pill-${role}` : 'nav-active-pill'}
                    data-slot="nav-active-pill"
                    className="absolute inset-0 rounded-[20px] bg-bg-muted"
                    transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                  />
                )}
                <Icon
                  className={cn('relative size-6 text-text-primary transition-opacity duration-200')}
                  strokeWidth={2}
                  aria-hidden
                />
                <span
                  className={cn(
                    'relative truncate text-label transition-colors duration-200',
                    active ? 'text-text-primary' : 'font-medium text-text-secondary',
                  )}
                >
                  {item.label}
                </span>
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

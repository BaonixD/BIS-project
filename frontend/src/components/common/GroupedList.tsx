import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { ChevronRight, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

/** Figma Profile: a titled white card on the subtle page background. */
export function GroupedSection({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="flex w-full flex-col gap-2">
      {title && <h2 className="px-4 text-callout text-text-secondary">{title}</h2>}
      <div className="flex w-full flex-col overflow-hidden rounded-lg bg-bg-canvas">{children}</div>
    </section>
  )
}

interface GroupedRowProps {
  icon: LucideIcon
  /** Replaces the icon inside the tile (e.g. the Google logo). */
  iconNode?: ReactNode
  /** Background of the 30px icon tile, e.g. `bg-accent-success`. */
  tone: string
  title: string
  value?: ReactNode
  to?: string
  onClick?: () => void
  disabled?: boolean
  chevron?: boolean
}

function Tile({ icon: Icon, iconNode, tone }: Pick<GroupedRowProps, 'icon' | 'iconNode' | 'tone'>) {
  return (
    <span className={cn('flex size-[30px] shrink-0 items-center justify-center rounded-[8px] text-text-inverse', tone)}>
      {iconNode ?? <Icon className="size-[18px]" strokeWidth={2.25} aria-hidden />}
    </span>
  )
}

/** One row: colored icon tile, title, optional value and a chevron when it navigates; inset divider between rows. */
export function GroupedRow({ icon, iconNode, tone, title, value, to, onClick, disabled, chevron }: GroupedRowProps) {
  const navigates = chevron ?? Boolean(to || onClick)
  const content = (
    <>
      <Tile icon={icon} iconNode={iconNode} tone={tone} />
      <span className="flex min-h-14 min-w-0 flex-1 items-center gap-2 border-t border-border-default py-3 pr-4 group-first/row:border-t-0">
        <span className="min-w-0 flex-1 truncate text-body-medium text-text-primary">{title}</span>
        {value !== undefined && <span className="max-w-[55%] truncate text-callout text-text-secondary">{value}</span>}
        {navigates && <ChevronRight className="size-5 shrink-0 text-text-tertiary" strokeWidth={2} aria-hidden />}
      </span>
    </>
  )
  const className =
    'group/row flex w-full items-center gap-3.5 pl-4 text-left outline-none transition-colors active:bg-bg-subtle focus-visible:bg-bg-subtle disabled:opacity-40'
  if (to) {
    return (
      <Link to={to} className={className}>
        {content}
      </Link>
    )
  }
  if (onClick) {
    return (
      <button type="button" onClick={onClick} disabled={disabled} className={className}>
        {content}
      </button>
    )
  }
  return <div className={className}>{content}</div>
}

/** Header card: avatar, name, subtitle and a chevron to the settings screen. */
export function ProfileHeaderCard({ avatar, name, subtitle, to }: { avatar: ReactNode; name: ReactNode; subtitle: ReactNode; to: string }) {
  return (
    <Link
      to={to}
      className="flex w-full items-center gap-4 rounded-lg bg-bg-canvas p-4 outline-none transition-colors active:bg-bg-muted focus-visible:ring-2 focus-visible:ring-bg-inverse"
    >
      {avatar}
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="truncate text-headline text-text-primary">{name}</span>
        <span className="truncate text-callout text-text-secondary">{subtitle}</span>
      </span>
      <ChevronRight className="size-6 shrink-0 text-text-tertiary" strokeWidth={2} aria-hidden />
    </Link>
  )
}

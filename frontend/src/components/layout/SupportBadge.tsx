import { useSupportUnread } from '@/hooks/use-support'
import { t, useLocale } from '@/i18n/core'
import { cn } from '@/lib/utils'

/** Unread support messages as a small count; nothing when all is read. */
export function SupportBadge({ className }: { className?: string }) {
  useLocale()
  const unread = useSupportUnread().data?.count ?? 0
  if (unread === 0) return null
  return (
    <span
      aria-label={t('Непрочитанных: {p0}', { p0: unread })}
      className={cn(
        'inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-brand-gold px-1 text-[11px] leading-none font-bold text-[#111]',
        className,
      )}
    >
      {unread > 99 ? '99+' : unread}
    </span>
  )
}

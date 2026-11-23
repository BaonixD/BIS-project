import { Link } from 'react-router'
import { MessageCircle } from 'lucide-react'
import { useSession } from '@/auth/use-session'
import { useSupportUnread } from '@/hooks/use-support'
import { StatusPill } from '@/components/ui-kit'
import { t, useLocale } from '@/i18n/core'

export function SupportLink({ rideId, compact = false }: { rideId?: string; compact?: boolean }) {
  useLocale()
  const { user } = useSession()
  const unread = useSupportUnread()
  const base =
    user?.role === 'admin'
      ? '/admin/support'
      : user?.role === 'driver'
        ? '/driver/support'
        : '/support'
  return (
    <Link
      to={rideId ? `${base}?ride_id=${rideId}` : base}
      className={`inline-flex items-center gap-2 rounded-md outline-none focus-visible:ring-2 ${compact ? 'px-3 py-2 text-caption' : 'bg-bg-canvas p-4 text-callout'}`}
    >
      <MessageCircle className="size-5 shrink-0" />
      <span>{t(rideId ? 'Проблема с поездкой' : 'Поддержка')}</span>
      {!rideId && (unread.data?.count ?? 0) > 0 && (
        <StatusPill tone="info">{unread.data!.count}</StatusPill>
      )}
    </Link>
  )
}

import { PartyPopper, Trophy } from 'lucide-react'
import { useMemo } from 'react'
import { useSession } from '@/auth/use-session'
import { useProgress } from '@/hooks/use-progress'
import { t, useLocale } from '@/i18n/core'
import { progressNews } from '@/lib/progress'
import { goalTitle } from '@/lib/achievement-goals'
import { LevelCard } from './Achievements'

/** After a ride: XP it brought, a level-up and the achievements it unlocked. */
export function RideRewards() {
  useLocale()
  const query = useProgress({ fresh: true })
  const userId = useSession().user?.id
  const progress = query.isFetching ? undefined : query.data
  const news = useMemo(
    () => (progress && userId ? progressNews(userId, progress) : null),
    [progress, userId],
  )
  if (!progress || !news || progress.achievements.length === 0) return null
  return (
    <section aria-label={t('Награды за поездку')} className="flex w-full flex-col gap-2.5">
      {news.levelUp && (
        <p className="flex items-center justify-center gap-2 text-callout text-brand-sky-ink motion-safe:animate-badge-pop">
          <PartyPopper className="size-4" aria-hidden />
          {t('Новый уровень!')}
        </p>
      )}
      <LevelCard progress={progress} gainedXp={news.gainedXp} />
      {news.unlocked.map((code) => (
        <p
          key={code}
          className="flex items-center gap-2.5 rounded-lg bg-bg-canvas px-4 py-3 text-callout text-text-primary motion-safe:animate-badge-pop"
        >
          <span className="flex size-8 items-center justify-center rounded-full bg-brand-gold text-[#1b2a3a]">
            <Trophy className="size-4" aria-hidden />
          </span>
          {t('Новое достижение: {p0}', { p0: goalTitle(code) })}
        </p>
      ))}
    </section>
  )
}

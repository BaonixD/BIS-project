import { Flame, Target, Trophy } from 'lucide-react'
import { useMemo } from 'react'
import { useSession } from '@/auth/use-session'
import { Skeleton } from '@/components/ui-kit'
import { useProgress } from '@/hooks/use-progress'
import { getIntlLocale, t, useLocale } from '@/i18n/core'
import { formatXp, levelShare, levelTitle, progressNews, type Progress } from '@/lib/progress'
import { cn } from '@/lib/utils'
import { GOALS } from '@/lib/achievement-goals'
import { ErrorAlert } from './ErrorAlert'
import { KazakhMotif } from './Ornament'

type Goal = Progress['achievements'][number]

function number(value: number, digits = 0) {
  return new Intl.NumberFormat(getIntlLocale(), {
    maximumFractionDigits: digits,
  })
    .format(value)
    .replace(/\s/g, ' ')
}

function goalProgress(goal: Goal): string {
  if (goal.code === 'high_rating')
    return t('{p0} / 4,8 · оценок {p1} из {p2}', {
      p0: number(goal.current, 2),
      p1: goal.sample_count ?? 0,
      p2: goal.minimum_samples ?? 5,
    })
  return `${number(Math.min(goal.current, goal.target), 1)} / ${number(goal.target)}`
}

function Bar({ share, label, className }: { share: number; label: string; className?: string }) {
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(share * 100)}
      className={cn('h-2 overflow-hidden rounded-full bg-bg-muted', className)}
    >
      <div
        className="h-full rounded-full bg-linear-to-r from-brand-sky to-brand-gold transition-[width] duration-700"
        style={{ width: `${Math.max(share * 100, share > 0 ? 4 : 0)}%` }}
      />
    </div>
  )
}

export function LevelBadge({ number: level, className }: { number: number; className?: string }) {
  return (
    <span
      className={cn(
        'flex size-14 shrink-0 items-center justify-center rounded-full bg-brand-sky-soft text-title text-brand-sky-ink ring-2 ring-brand-gold ring-offset-2 ring-offset-bg-canvas',
        className,
      )}
      aria-hidden
    >
      {level}
    </span>
  )
}

/** Level, XP towards the next level and a gold/sky bar. */
export function LevelCard({ progress, gainedXp = 0 }: { progress: Progress; gainedXp?: number }) {
  useLocale()
  const { level, xp } = progress
  const locale = getIntlLocale()
  return (
    <div className="relative flex flex-col gap-3 overflow-hidden rounded-[20px] border border-brand-sky/30 bg-linear-to-br from-[#e9f8fb] via-[#eef8fa] to-[#fdf4d6] p-4 dark:from-[#0e2a31] dark:via-[#10242a] dark:to-[#2b2410]">
      <KazakhMotif className="pointer-events-none absolute right-3 bottom-2 h-10 w-[52px] text-brand-sky-ink/10" />
      <div className="flex items-center gap-3">
        <LevelBadge number={level.number} />
        <div className="flex min-w-0 flex-1 flex-col">
          <p className="text-label tracking-wide text-brand-sky-ink uppercase">
            {t('Уровень {p0}', { p0: level.number })}
          </p>
          <p className="truncate text-headline text-text-primary">{levelTitle(level.number)}</p>
        </div>
        <div className="flex flex-col items-end">
          <p className="text-callout text-text-primary tabular-nums">{formatXp(xp, locale)}</p>
          {gainedXp > 0 && (
            <p className="text-caption font-semibold text-accent-success motion-safe:animate-badge-pop">
              +{formatXp(gainedXp, locale)}
            </p>
          )}
        </div>
      </div>
      <Bar share={levelShare(level, xp)} label={t('Опыт до следующего уровня')} />
      <p className="text-caption text-text-secondary">
        {level.next_level_xp == null
          ? t('Максимальный уровень — вы настоящий Тулпар')
          : t('{p0} до уровня {p1}', {
              p0: formatXp(level.next_level_xp - xp, locale),
              p1: level.number + 1,
            })}
      </p>
    </div>
  )
}

function daysLeft(iso: string): number {
  return Math.max(1, Math.ceil((Date.parse(iso) - Date.now()) / 86_400_000))
}

function StreakAndQuest({ progress }: { progress: Progress }) {
  useLocale()
  const { streak, weekly_quest: quest } = progress
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="flex flex-col gap-1.5 rounded-lg border border-border-default bg-bg-canvas p-3.5">
        <Flame
          aria-hidden
          className={cn(
            'size-5',
            streak.current_weeks > 0 ? 'text-accent-warning' : 'text-text-tertiary',
          )}
        />
        <p className="text-callout text-text-primary">
          {t('{p0} нед. подряд', { p0: streak.current_weeks })}
        </p>
        <p className="text-caption text-text-secondary">
          {streak.current_weeks > 0 && !streak.active_this_week
            ? t('Прокатитесь на этой неделе, чтобы не потерять серию')
            : t('Лучшая серия: {p0}', { p0: streak.best_weeks })}
        </p>
      </div>
      <div
        className={cn(
          'flex flex-col gap-1.5 rounded-lg border bg-bg-canvas p-3.5',
          quest.completed ? 'border-accent-success' : 'border-border-default',
        )}
      >
        <div className="flex items-center justify-between gap-2">
          <Target aria-hidden className="size-5 text-brand-sky-ink" />
          <span className="rounded-full bg-brand-gold/25 px-2 py-0.5 text-label text-text-primary">
            +{formatXp(quest.reward_xp, getIntlLocale())}
          </span>
        </div>
        <p className="text-callout text-text-primary">
          {t('{p0} из {p1} поездок', {
            p0: Math.min(quest.current, quest.target),
            p1: quest.target,
          })}
        </p>
        <Bar share={Math.min(1, quest.current / quest.target)} label={t('Задание недели')} />
        <p className="text-caption text-text-secondary">
          {quest.completed
            ? t('Задание недели выполнено')
            : t('Задание недели · ещё {p0} дн.', {
                p0: daysLeft(quest.ends_at),
              })}
        </p>
      </div>
    </div>
  )
}

function GoalCard({ goal, fresh }: { goal: Goal; fresh: boolean }) {
  useLocale()
  const meta = GOALS()[goal.code]
  const Icon = meta?.icon ?? Trophy
  const share = goal.target ? Math.min(1, Math.max(0, goal.current / goal.target)) : 0
  return (
    <div
      className={cn(
        'flex flex-col gap-2 rounded-lg border bg-bg-canvas p-3.5',
        goal.unlocked ? 'border-brand-gold/70' : 'border-border-default',
        fresh && 'motion-safe:animate-badge-pop',
      )}
    >
      <div className="flex items-center gap-2.5">
        <span
          className={cn(
            'flex size-9 shrink-0 items-center justify-center rounded-full',
            goal.unlocked ? 'bg-brand-gold text-[#1b2a3a]' : 'bg-bg-muted text-text-tertiary',
          )}
        >
          <Icon className="size-[18px]" aria-hidden />
        </span>
        <div className="flex min-w-0 flex-col">
          <p className="truncate text-callout text-text-primary">{meta?.title ?? goal.code}</p>
          <p className="truncate text-caption text-text-secondary">{meta?.hint}</p>
        </div>
      </div>
      {goal.unlocked ? (
        <p className="text-caption font-semibold text-brand-sky-ink">
          {fresh ? t('Новое!') : t('Получено')} · +{formatXp(goal.xp, getIntlLocale())}
        </p>
      ) : (
        <>
          <Bar share={share} label={meta?.title ?? goal.code} className="h-1.5" />
          <p className="text-caption text-text-secondary tabular-nums">{goalProgress(goal)}</p>
        </>
      )}
    </div>
  )
}

/** Profile block: level and XP, the weekly streak and quest, then every achievement. */
export function Achievements() {
  useLocale()
  const query = useProgress()
  const userId = useSession().user?.id
  const progress = query.data
  const news = useMemo(
    () => (progress && userId ? progressNews(userId, progress) : null),
    [progress, userId],
  )
  const unlocked = progress?.achievements.filter((goal) => goal.unlocked).length ?? 0
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-headline">{t('Достижения')}</h2>
        {progress && progress.achievements.length > 0 && (
          <p className="text-caption text-text-secondary">
            {t('Открыто {p0} из {p1}', {
              p0: unlocked,
              p1: progress.achievements.length,
            })}
          </p>
        )}
      </div>
      <ErrorAlert error={query.error} />
      {query.isPending && <Skeleton className="h-40 rounded-lg" />}
      {progress && progress.achievements.length > 0 && (
        <>
          <LevelCard progress={progress} />
          <StreakAndQuest progress={progress} />
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {[...progress.achievements]
              .sort((a, b) => Number(b.unlocked) - Number(a.unlocked))
              .map((goal) => (
                <GoalCard
                  key={goal.code}
                  goal={goal}
                  fresh={news?.unlocked.includes(goal.code) ?? false}
                />
              ))}
          </div>
        </>
      )}
    </section>
  )
}

import { useQuery } from '@tanstack/react-query'
import { Award, CheckCircle2 } from 'lucide-react'
import { api, unwrap } from '@/api'
import { t, useLocale, getIntlLocale } from '@/i18n/core'
import { Skeleton } from '@/components/ui-kit'
import { ErrorAlert } from './ErrorAlert'

const titles = () => ({ first_ride: t('Первая поездка'), regular_passenger: t('Частый пассажир'), feedback: t('Обратная связь'), first_order: t('Первый заказ'), experienced_driver: t('Опытный водитель'), high_rating: t('Высокая оценка') } as Record<string, string>)

export function Achievements() {
  useLocale()
  const query = useQuery({ queryKey: ['achievements'], queryFn: () => unwrap(api.GET('/api/v1/users/me/achievements')) })
  return <section className="flex flex-col gap-3"><h2 className="text-headline">{t('Достижения')}</h2><ErrorAlert error={query.error} />{query.isPending && <Skeleton className="h-28 rounded-lg" />}<div className="grid gap-3 sm:grid-cols-3">{query.data?.achievements.map((goal) => <div key={goal.code} className={`rounded-lg border p-4 ${goal.unlocked ? 'border-accent-success bg-bg-canvas' : 'border-border-default bg-bg-canvas'}`}><div className="flex items-center gap-2">{goal.unlocked ? <CheckCircle2 className="size-5 text-accent-success" /> : <Award className="size-5 text-text-secondary" />}<p className="text-callout">{titles()[goal.code] ?? goal.code}</p></div><p className="mt-3 text-caption text-text-secondary">{goal.code === 'high_rating' ? `${new Intl.NumberFormat(getIntlLocale(), { maximumFractionDigits: 2 }).format(goal.current)} / 4.8` : `${Math.min(goal.current, goal.target)} / ${goal.target}`}</p>{goal.minimum_samples != null && <p className="mt-1 text-caption text-text-secondary">{t('Оценок: {p0} из {p1}', { p0: goal.sample_count ?? 0, p1: goal.minimum_samples })}</p>}<div className="mt-2 h-1.5 overflow-hidden rounded-full bg-bg-muted" role="progressbar" aria-label={titles()[goal.code]} aria-valuemin={0} aria-valuemax={goal.target} aria-valuenow={Math.min(goal.current, goal.target)}><div className={`h-full ${goal.unlocked ? 'bg-accent-success' : 'bg-text-tertiary'}`} style={{ width: `${Math.min(100, Math.max(0, goal.current / goal.target * 100))}%` }} /></div></div>)}</div></section>
}

import type { components } from '@/api/schema'
import { t } from '@/i18n/core'

export type Level = components['schemas']['Level']
export type Progress = components['schemas']['Progress']

const UNLOCKS_KEY = 'bis.progress.unlocked:'
const XP_KEY = 'bis.progress.xp:'

/** Way from the start of the level to the next one, 0…1; full on the top level. */
export function levelShare(level: Level, xp: number): number {
  if (level.next_level_xp == null) return 1
  const span = level.next_level_xp - level.level_start_xp
  return Math.min(1, Math.max(0, (xp - level.level_start_xp) / span))
}

const LEVEL_TITLES = () => [
  t('Новичок'),
  t('Попутчик'),
  t('Путешественник'),
  t('Знаток города'),
  t('Странник степи'),
  t('Покоритель Алатау'),
  t('Батыр дорог'),
  t('Тулпар'),
]

export function levelTitle(number: number): string {
  const titles = LEVEL_TITLES()
  return titles[Math.min(Math.max(number, 1), titles.length) - 1]!
}

function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* Storage may be disabled: celebrations are a convenience. */
  }
}

/** Unlocked codes not seen on this device; the first visit only remembers them. */
export function takeNewUnlocks(userId: string, codes: string[]): string[] {
  const saved = read(UNLOCKS_KEY + userId)
  write(UNLOCKS_KEY + userId, JSON.stringify(codes))
  if (saved === null) return []
  let seen: unknown
  try {
    seen = JSON.parse(saved)
  } catch {
    return []
  }
  const known = new Set(Array.isArray(seen) ? seen : [])
  return codes.filter((code) => !known.has(code))
}

/** XP gained since the last visit on this device; 0 on the first one. */
export function takeXpGain(userId: string, xp: number): number {
  const saved = read(XP_KEY + userId)
  write(XP_KEY + userId, String(xp))
  const before = saved === null ? Number.NaN : Number(saved)
  return Number.isFinite(before) ? Math.max(0, xp - before) : 0
}

export interface ProgressNews {
  gainedXp: number
  unlocked: string[]
  levelUp: boolean
}

const newsCache = new Map<string, ProgressNews>()

/** Reads and remembers the news once per user and XP, so a repeated render sees the same. */
export function progressNews(userId: string, progress: Progress): ProgressNews {
  const unlockedCodes = progress.achievements
    .filter((goal) => goal.unlocked)
    .map((goal) => goal.code)
  const key = `${userId}:${progress.xp}:${unlockedCodes.join(',')}`
  let news = newsCache.get(key)
  if (!news) {
    const gainedXp = takeXpGain(userId, progress.xp)
    news = {
      gainedXp,
      unlocked: takeNewUnlocks(userId, unlockedCodes),
      levelUp: gainedXp > 0 && progress.xp - gainedXp < progress.level.level_start_xp,
    }
    newsCache.set(key, news)
  }
  return news
}

/** «1 170 XP» with ordinary spaces. */
export function formatXp(xp: number, locale: string): string {
  return `${new Intl.NumberFormat(locale).format(xp).replace(/\s/g, ' ')} XP`
}

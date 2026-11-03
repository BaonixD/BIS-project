import type { PassengerRatingTag as RatingTag, RatingRequest } from '@/api/passenger-types'

/** Full labels (details, history) and the short ones of the compact card in Figma 5:499. */
export const RATING_TAG_LABELS: Record<RatingTag, string> = {
  polite: 'Вежливый',
  clean_car: 'Чистая машина',
  smooth_driving: 'Аккуратная езда',
  knows_route: 'Знает дорогу',
}

export const COMPACT_RATING_TAGS: { tag: RatingTag; label: string }[] = [
  { tag: 'polite', label: 'Вежливый' },
  { tag: 'clean_car', label: 'Чисто' },
  { tag: 'smooth_driving', label: 'Аккуратно' },
]

export const COMMENT_MAX_LENGTH = 500

export function buildRating(stars: number, tags: readonly RatingTag[], comment: string): RatingRequest & { comment: string | null } {
  if (!Number.isInteger(stars) || stars < 1 || stars > 5) throw new RangeError('stars must be 1..5')
  const trimmed = comment.trim()
  return { stars, tags: [...new Set(tags)], comment: trimmed ? trimmed.slice(0, COMMENT_MAX_LENGTH) : null }
}

export function toggleTag(tags: readonly RatingTag[], tag: RatingTag): RatingTag[] {
  return tags.includes(tag) ? tags.filter((t) => t !== tag) : [...tags, tag]
}

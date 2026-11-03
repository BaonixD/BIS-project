export const RELEASE_REASONS = ['Пассажир не вышел', 'Поломка', 'Далеко ехать', 'Другое'] as const
export type ReleaseReason = (typeof RELEASE_REASONS)[number]

const MAX_REASON = 200

/** `POST /rides/{id}/release` body: the chosen reason with the optional comment (1–200 chars). */
export function buildReleaseBody(reason: ReleaseReason, comment: string): { reason: string } {
  const note = comment.trim()
  const text = reason === 'Другое' ? note || reason : note ? `${reason}: ${note}` : reason
  return { reason: text.slice(0, MAX_REASON) }
}

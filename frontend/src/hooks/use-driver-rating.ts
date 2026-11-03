import { useMutation, useQueryClient } from '@tanstack/react-query'
import { isApiError } from '@/api'
import {
  postPassengerRating,
  RATING_ALREADY_EXISTS,
  type PassengerRatingRequest,
  type PassengerTag,
} from '@/api/next-contract-driver'

/** Rating body: 1–5 stars, unique tags in a stable order, a trimmed comment or null. */
export function buildRatingBody(stars: number, tags: Iterable<PassengerTag>, comment = ''): PassengerRatingRequest {
  const order: PassengerTag[] = ['on_time', 'polite', 'clean']
  const chosen = new Set(tags)
  return {
    stars: Math.min(5, Math.max(1, Math.round(stars))),
    tags: order.filter((tag) => chosen.has(tag)),
    comment: comment.trim() || null,
  }
}

/** The driver rates the passenger once; a repeat (`rating_already_exists`) counts as done. */
export function useRatePassenger(rideId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: PassengerRatingRequest) => {
      try {
        await postPassengerRating(rideId, body)
      } catch (error) {
        if (!isApiError(error, RATING_ALREADY_EXISTS)) throw error
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rides', 'history'] }),
  })
}

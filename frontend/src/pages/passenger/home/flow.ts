import type { Coordinates, PaymentMethod } from '@/api'
import type { Tariff } from '@/api/passenger-types'

export type Target = 'pickup' | 'dropoff'

export type Step =
  | { name: 'home' }
  | { name: 'search'; target: Target }
  | { name: 'map'; target: Target; start: Coordinates }
  | { name: 'choose' }

/** Router state for «Заказать снова», «Искать снова» and «Изменить маршрут». */
export interface ReorderState {
  pickup: Coordinates
  dropoff: Coordinates
  tariff?: Tariff
  paymentMethod?: PaymentMethod
  step: 'choose' | 'search'
}

export function isReorderState(value: unknown): value is ReorderState {
  const state = value as ReorderState | null
  return Boolean(state?.pickup && state.dropoff && (state.step === 'choose' || state.step === 'search'))
}

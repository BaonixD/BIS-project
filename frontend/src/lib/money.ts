/** The part of a ride paid in money: bonuses cover the rest (at most half). */
export function moneyDue(ride: { amount_kzt: number; bonus_kzt?: number }): number {
  return ride.amount_kzt - (ride.bonus_kzt ?? 0)
}

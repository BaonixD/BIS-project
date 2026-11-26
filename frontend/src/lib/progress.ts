import type { components } from '@/api/schema'

export type Level = components['schemas']['Level']

export function levelShare(_level: Level, _xp: number): number {
  return 0
}
export function levelTitle(_number: number): string {
  return ''
}
export function takeNewUnlocks(_userId: string, _codes: string[]): string[] {
  return []
}
export function takeXpGain(_userId: string, _xp: number): number {
  return 0
}

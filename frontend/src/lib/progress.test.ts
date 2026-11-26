import { beforeEach, describe, expect, it, vi } from 'vitest'
import { memoryStorage } from '@/test/fake-api'
import { levelShare, levelTitle, takeNewUnlocks, takeXpGain } from './progress'

beforeEach(() => vi.stubGlobal('localStorage', memoryStorage()))

describe('levels', () => {
  it('shows the share of the way to the next level and a full bar on the top level', () => {
    expect(levelShare({ number: 3, level_start_xp: 800, next_level_xp: 1500 }, 1150)).toBe(0.5)
    expect(levelShare({ number: 8, level_start_xp: 9000, next_level_xp: null }, 12000)).toBe(1)
  })

  it('names every level and keeps the last name above the table', () => {
    expect(levelTitle(1)).toBe('Новичок')
    expect(levelTitle(8)).toBe('Тулпар')
    expect(levelTitle(12)).toBe('Тулпар')
  })
})

describe('celebrations', () => {
  it('stays quiet on the first visit, then reports only new unlocks once', () => {
    expect(takeNewUnlocks('u1', ['first_ride'])).toEqual([])
    expect(takeNewUnlocks('u1', ['first_ride', 'night_owl'])).toEqual(['night_owl'])
    expect(takeNewUnlocks('u1', ['first_ride', 'night_owl'])).toEqual([])
    expect(takeNewUnlocks('u2', ['first_ride', 'night_owl'])).toEqual([])
  })

  it('reports the XP gained since the last visit', () => {
    expect(takeXpGain('u1', 300)).toBe(0)
    expect(takeXpGain('u1', 470)).toBe(170)
    expect(takeXpGain('u1', 470)).toBe(0)
  })
})

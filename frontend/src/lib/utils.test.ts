import { describe, expect, it } from 'vitest'
import { cn } from './utils'

describe('cn', () => {
  it('keeps a Figma text style next to a text colour', () => {
    expect(cn('text-body-medium', 'text-accent-danger')).toBe('text-body-medium text-accent-danger')
  })

  it('lets a later text style replace an earlier one', () => {
    expect(cn('text-callout', 'text-caption')).toBe('text-caption')
  })
})

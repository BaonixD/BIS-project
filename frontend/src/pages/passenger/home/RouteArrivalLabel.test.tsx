import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { RouteResult } from '@/api'
import { setLocale } from '@/i18n/core'
import { ROUTE } from '@/pages/passenger/test/fixtures'
import { RouteArrivalLabel } from './RouteArrivalLabel'

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-11-16T23:50:00+05:00'))
})
afterEach(() => {
  act(() => setLocale('ru'))
  vi.useRealTimers()
})

it('shows arrival across midnight with explicit traffic metadata, and updates when time passes', () => {
  render(
    <RouteArrivalLabel
      route={{ ...ROUTE, provider: 'mapbox', traffic_mode: 'live_or_typical' } as RouteResult}
    />,
  )
  expect(screen.getByText('Прибытие ≈00:15')).toBeInTheDocument()
  expect(screen.getByText('С учётом дорожной ситуации')).toBeInTheDocument()
  act(() => vi.advanceTimersByTime(60_000))
  expect(screen.getByText('Прибытие ≈00:16')).toBeInTheDocument()
})

it('does not infer traffic from the provider name', () => {
  render(
    <RouteArrivalLabel
      route={{ ...ROUTE, provider: 'mapbox', traffic_mode: 'none' } as RouteResult}
    />,
  )
  expect(screen.getByText('Без учёта актуальных пробок')).toBeInTheDocument()
  expect(screen.queryByText('С учётом дорожной ситуации')).not.toBeInTheDocument()
})

it('localizes the map label in English and Kazakh', () => {
  render(<RouteArrivalLabel route={{ ...ROUTE, traffic_mode: 'live_or_typical' } as RouteResult} />)
  act(() => setLocale('en'))
  expect(screen.getByText('Considering traffic conditions')).toBeInTheDocument()
  act(() => setLocale('kk'))
  expect(screen.getByText('Жол жағдайы ескерілген')).toBeInTheDocument()
})

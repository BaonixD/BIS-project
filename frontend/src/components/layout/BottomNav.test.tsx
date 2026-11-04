import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { UserRole } from '@/api'
import { BottomNav } from './BottomNav'
import { TopBar } from './TopBar'

function renderNav(role: UserRole, path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <BottomNav role={role} />
    </MemoryRouter>,
  )
  return screen.getByRole('navigation', { name: 'Основная навигация' })
}

function labels(nav: HTMLElement) {
  return within(nav)
    .getAllByRole('link')
    .map((link) => link.textContent)
}

function activeLabel(nav: HTMLElement) {
  return within(nav)
    .getAllByRole('link')
    .filter((link) => link.getAttribute('aria-current') === 'page')
    .map((link) => link.textContent)
}

describe('BottomNav', () => {
  it.each([
    ['passenger', ['Такси', 'История', 'Профиль']],
    ['driver', ['Смена', 'История', 'Профиль']],
    ['admin', ['Водители', 'Поездки', 'Люди']],
  ] as const)('shows the %s items from the Figma BottomNav', (role, expected) => {
    expect(labels(renderNav(role, '/'))).toEqual(expected)
  })

  it.each([
    ['passenger', '/', 'Такси'],
    ['passenger', '/ride/42', 'Такси'],
    ['passenger', '/history', 'История'],
    ['passenger', '/profile', 'Профиль'],
    ['driver', '/driver', 'Смена'],
    ['driver', '/driver/history', 'История'],
    ['driver', '/driver/profile', 'Профиль'],
    ['admin', '/admin', 'Водители'],
    ['admin', '/admin/rides', 'Поездки'],
    ['admin', '/admin/users', 'Люди'],
  ] as const)('marks exactly one active item for %s at %s', (role, path, expected) => {
    expect(activeLabel(renderNav(role, path))).toEqual([expected])
  })

  it('draws the active capsule only behind the active item', () => {
    const nav = renderNav('passenger', '/history')
    const capsules = nav.querySelectorAll('[data-slot="nav-active-pill"]')
    expect(capsules).toHaveLength(1)
    expect(capsules[0]?.closest('a')).toHaveTextContent('История')
  })
})

describe('TopBar', () => {
  it('shows the role links and the account', () => {
    render(
      <MemoryRouter initialEntries={['/history']}>
        <TopBar role="passenger" displayName="Айгерим" />
      </MemoryRouter>,
    )
    const nav = screen.getByRole('navigation', { name: 'Разделы' })
    expect(activeLabel(nav)).toEqual(['История'])
    expect(screen.getByText('BIS Taxi')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Айгерим/ })).toHaveAttribute('href', '/profile')
  })
})

describe('TopBar logout', () => {
  const renderBar = (role: UserRole, onLogout: () => void) =>
    render(
      <MemoryRouter initialEntries={['/']}>
        <TopBar role={role} displayName="admin" onLogout={onLogout} />
      </MemoryRouter>,
    )

  it('lets the admin, who has no profile page, log out', async () => {
    const onLogout = vi.fn()
    renderBar('admin', onLogout)
    await userEvent.click(screen.getByRole('button', { name: 'Выйти' }))
    expect(onLogout).toHaveBeenCalledOnce()
  })

  it('leaves logout to the profile page for other roles', () => {
    renderBar('passenger', vi.fn())
    expect(screen.queryByRole('button', { name: 'Выйти' })).not.toBeInTheDocument()
  })
})

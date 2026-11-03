import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { MyProfile } from '@/api'
import { LoginMethodRow } from './LoginMethodRow'

const base: MyProfile = {
  id: 'u1',
  username: 'aigerim',
  role: 'passenger',
  created_at: '2026-11-03T09:00:00Z',
  display_name: 'Айгерим',
  phone: null,
  rating: { average: null, count: 0 },
  login_method: 'password',
  email: null,
}

describe('LoginMethodRow', () => {
  it('shows Google with the account email', () => {
    render(<LoginMethodRow profile={{ ...base, login_method: 'google', email: 'aigerim@gmail.com' }} />)
    expect(screen.getByText('Google · aigerim@gmail.com')).toBeInTheDocument()
  })

  it('shows the password login with the username when asked', () => {
    render(<LoginMethodRow profile={base} showUsername />)
    expect(screen.getByText('Логин и пароль · @aigerim')).toBeInTheDocument()
  })
})

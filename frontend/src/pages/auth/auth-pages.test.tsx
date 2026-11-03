import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider, useLocation } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SessionContext, type SessionContextValue } from '@/auth/session-context'
import { LoginPage } from './LoginPage'
import { RegisterPage } from './RegisterPage'

const providers = vi.hoisted(() => ({ google_client_id: null as string | null }))

vi.mock('@/auth/session-api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/auth/session-api')>()),
  fetchAuthProviders: vi.fn(async () => ({ ...providers })),
}))

function mutation() {
  return { mutate: vi.fn(), mutateAsync: vi.fn(async () => ({})), reset: vi.fn(), isPending: false, error: null }
}

function LocationProbe() {
  const location = useLocation()
  return <p data-testid="location">{`${location.pathname} ${JSON.stringify(location.state)}`}</p>
}

function renderAt(path: string, state?: unknown) {
  const session = {
    status: 'anonymous',
    user: null,
    login: mutation(),
    register: mutation(),
    logout: mutation(),
    googleLogin: mutation(),
  } as unknown as SessionContextValue
  const router = createMemoryRouter(
    [
      { path: '/login', element: <><LoginPage /><LocationProbe /></> },
      { path: '/register', element: <><RegisterPage /><LocationProbe /></> },
    ],
    { initialEntries: [{ pathname: path, state }] },
  )
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <SessionContext.Provider value={session}>
        <RouterProvider router={router} />
      </SessionContext.Provider>
    </QueryClientProvider>,
  )
  return session
}

beforeEach(() => {
  providers.google_client_id = null
})

describe('LoginPage (Figma 4:2)', () => {
  it('shows the Figma texts and fields', () => {
    renderAt('/login')
    expect(screen.getByRole('heading', { name: 'С возвращением' })).toBeInTheDocument()
    expect(screen.getByText('Войдите, чтобы заказать поездку по Алматы')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Имя пользователя')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Пароль')).toHaveAttribute('type', 'password')
    expect(screen.getByRole('link', { name: 'Зарегистрироваться' })).toHaveAttribute('href', '/register')
  })

  it('signs in with the typed credentials', async () => {
    const session = renderAt('/login')
    await userEvent.type(screen.getByPlaceholderText('Имя пользователя'), 'aigerim')
    await userEvent.type(screen.getByPlaceholderText('Пароль'), 'correct-horse')
    await userEvent.click(screen.getByRole('button', { name: 'Войти' }))
    expect(session.login.mutate).toHaveBeenCalledWith({ username: 'aigerim', password: 'correct-horse' })
  })

  it('hides Google sign-in when the server has no Google client', async () => {
    renderAt('/login')
    await waitFor(() => expect(screen.queryByText('или')).not.toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /Продолжить с Google/ })).not.toBeInTheDocument()
  })

  it('offers Google sign-in when the server returns a client id', async () => {
    providers.google_client_id = 'client-123.apps.googleusercontent.com'
    renderAt('/login')
    expect(await screen.findByRole('button', { name: /Продолжить с Google/ })).toBeInTheDocument()
    expect(screen.getByText('или')).toBeInTheDocument()
  })

  it('prefills the username after registration', () => {
    renderAt('/login', { username: 'new_driver' })
    expect(screen.getByPlaceholderText('Имя пользователя')).toHaveValue('new_driver')
  })
})

describe('RegisterPage (Figma 4:43)', () => {
  it('picks the role with cards, passenger first', async () => {
    renderAt('/register')
    const group = screen.getByRole('radiogroup', { name: 'Роль' })
    expect(group).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Пассажир/ })).toHaveAttribute('aria-checked', 'true')
    await userEvent.click(screen.getByRole('radio', { name: /Водитель/ }))
    expect(screen.getByRole('radio', { name: /Водитель/ })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: /Пассажир/ })).toHaveAttribute('aria-checked', 'false')
  })

  it('registers and sends the user to sign in with the new username', async () => {
    const session = renderAt('/register')
    await userEvent.click(screen.getByRole('radio', { name: /Водитель/ }))
    await userEvent.type(screen.getByPlaceholderText(/Имя пользователя/), 'new_driver')
    await userEvent.type(screen.getByPlaceholderText(/Пароль/), 'long-enough-pass')
    await userEvent.click(screen.getByRole('button', { name: 'Создать аккаунт' }))
    expect(session.register.mutateAsync).toHaveBeenCalledWith({
      username: 'new_driver',
      password: 'long-enough-pass',
      role: 'driver',
    })
    await waitFor(() =>
      expect(screen.getByTestId('location')).toHaveTextContent('/login {"username":"new_driver"}'),
    )
  })

  it('goes back to sign-in with the arrow', async () => {
    renderAt('/register')
    await userEvent.click(screen.getByRole('link', { name: 'Назад ко входу' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/login')
  })
})

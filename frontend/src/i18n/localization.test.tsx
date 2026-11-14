import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { LoginPage } from '@/pages/auth/LoginPage'
import { LanguageSwitcher } from './LanguageSwitcher'
import { LOCALE_STORAGE_KEY, setLocale } from './core'
import { RIDE_STATUS_LABELS } from '@/lib/labels'
import { useLocale } from './core'
import { createGeocoder } from '@/lib/geocoding'
import { memoryStorage } from '@/test/fake-api'

vi.stubGlobal('localStorage', memoryStorage())
vi.mock('@/auth/session-api', () => ({
  fetchAuthProviders: async () => ({ google_client_id: null }),
}))
vi.mock('@/auth/use-session', () => ({
  useSession: () => ({
    login: { mutate: vi.fn(), reset: vi.fn(), error: null, isPending: false },
    googleLogin: { mutate: vi.fn(), reset: vi.fn(), error: null, isPending: false },
  }),
}))
beforeEach(() => act(() => setLocale('ru')))
afterEach(() => act(() => setLocale('ru')))

it('switches the login page between three languages without clearing the form', async () => {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  await userEvent.type(screen.getByPlaceholderText('Имя пользователя'), 'aigerim')
  await userEvent.type(screen.getByPlaceholderText('Пароль'), 'secret-password')
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Язык интерфейса' }), 'en')
  expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  expect(screen.getByPlaceholderText('Username')).toHaveValue('aigerim')
  expect(screen.getByPlaceholderText('Password')).toHaveValue('secret-password')
  expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Interface language' }), 'kk')
  expect(screen.getByRole('heading', { name: 'Қайта қош келдіңіз' })).toBeInTheDocument()
  expect(screen.getByPlaceholderText('Пайдаланушы аты')).toHaveValue('aigerim')
  expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('kk')
  expect(document.documentElement.lang).toBe('kk')
})

function StatusReader() {
  useLocale()
  return (
    <>
      <LanguageSwitcher />
      <p>{RIDE_STATUS_LABELS().assigned}</p>
    </>
  )
}

it('refreshes module-level status labels without remounting a screen', async () => {
  render(<StatusReader />)
  expect(screen.getByText('Водитель едет к вам')).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByRole('combobox'), 'en')
  expect(screen.getByText('Your driver is on the way')).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByRole('combobox'), 'kk')
  expect(screen.getByText('Жүргізуші сізге келе жатыр')).toBeInTheDocument()
})

it('requests addresses in the chosen language and separates cached results by language', async () => {
  const fetch = vi.fn(async (url: string) => {
    const language = new URL(url).searchParams.get('accept-language')
    return new Response(
      JSON.stringify([
        {
          place_id: 1,
          lat: '43.24',
          lon: '76.95',
          name: language === 'en' ? 'Airport' : 'Әуежай',
          display_name: 'Almaty',
        },
      ]),
      { status: 200 },
    )
  })
  const geocoder = createGeocoder({
    fetch: fetch as unknown as typeof globalThis.fetch,
    minIntervalMs: 0,
  })
  setLocale('en')
  expect((await geocoder.search('airport'))[0]?.title).toBe('Airport')
  setLocale('kk')
  expect((await geocoder.search('airport'))[0]?.title).toBe('Әуежай')
  setLocale('en')
  expect((await geocoder.search('airport'))[0]?.title).toBe('Airport')
  expect(fetch).toHaveBeenCalledTimes(2)
})

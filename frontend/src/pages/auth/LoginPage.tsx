import { useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router'
import { Lock, User } from 'lucide-react'
import { useAuthProviders } from '@/auth/use-auth-providers'
import { useSession } from '@/auth/use-session'
import { Button, Input } from '@/components/ui-kit'
import { AuthHeading, AuthLayout, FormError } from './AuthLayout'
import { GoogleSignInButton } from './GoogleSignInButton'

function Logo() {
  return (
    <div className="flex items-center gap-2">
      <span className="flex size-10 items-center justify-center rounded-[10px] bg-bg-inverse text-headline text-text-inverse">
        B
      </span>
      <span className="text-headline text-text-primary">BIS Taxi</span>
    </div>
  )
}

function OrDivider() {
  return (
    <div className="flex items-center gap-3" aria-hidden>
      <span className="h-px flex-1 bg-border-default" />
      <span className="text-caption text-text-tertiary">или</span>
      <span className="h-px flex-1 bg-border-default" />
    </div>
  )
}

/** Figma «Auth / Login» 4:2. */
export function LoginPage() {
  const { login, googleLogin } = useSession()
  const providers = useAuthProviders()
  const location = useLocation()
  const registered = (location.state as { username?: string } | null)?.username
  const [username, setUsername] = useState(registered ?? '')
  const [password, setPassword] = useState('')
  const googleClientId = providers.data?.google_client_id

  const submit = (event: FormEvent) => {
    event.preventDefault()
    googleLogin.reset()
    login.mutate({ username, password })
  }

  return (
    <AuthLayout top="login">
      <Logo />
      <AuthHeading title="С возвращением" subtitle="Войдите, чтобы заказать поездку по Алматы" />
      <form className="flex flex-col gap-6" onSubmit={submit}>
        <div className="flex flex-col gap-3">
          <Input
            icon={User}
            name="username"
            placeholder="Имя пользователя"
            autoComplete="username"
            autoCapitalize="none"
            required
            autoFocus={!registered}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
          <Input
            icon={Lock}
            name="password"
            type="password"
            placeholder="Пароль"
            autoComplete="current-password"
            required
            autoFocus={Boolean(registered)}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <FormError error={login.error ?? googleLogin.error} />
        </div>
        <Button type="submit" className="w-full" loading={login.isPending}>
          Войти
        </Button>
      </form>
      {googleClientId && (
        <>
          <OrDivider />
          <GoogleSignInButton
            clientId={googleClientId}
            disabled={googleLogin.isPending}
            onCredential={(credential) => {
              login.reset()
              googleLogin.mutate(credential)
            }}
          />
        </>
      )}
      <p className="text-center text-callout text-text-primary">
        Нет аккаунта? <Link to="/register" className="outline-none focus-visible:underline">Зарегистрироваться</Link>
      </p>
    </AuthLayout>
  )
}

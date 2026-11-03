import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { useSession } from '@/auth/use-session'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AuthLayout } from './AuthLayout'

export function LoginPage() {
  const { login } = useSession()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    login.mutate({ username, password })
  }

  return (
    <AuthLayout title="Вход" description="BIS Такси — Алматы">
      <form className="grid gap-4" onSubmit={submit}>
        <div className="grid gap-2">
          <Label htmlFor="username">Имя пользователя</Label>
          <Input id="username" autoComplete="username" required value={username} onChange={(e) => setUsername(e.target.value)} />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="password">Пароль</Label>
          <Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <ErrorAlert error={login.error} />
        <Button type="submit" disabled={login.isPending}>Войти</Button>
        <p className="text-center text-sm text-muted-foreground">
          Нет аккаунта? <Link to="/register" className="text-foreground underline underline-offset-4">Регистрация</Link>
        </p>
      </form>
    </AuthLayout>
  )
}

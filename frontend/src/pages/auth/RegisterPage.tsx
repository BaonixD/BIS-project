import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import type { RegisterRequest } from '@/api'
import { useSession } from '@/auth/use-session'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AuthLayout } from './AuthLayout'

type PublicRole = RegisterRequest['role']

export function RegisterPage() {
  const { register, login } = useSession()
  const [role, setRole] = useState<PublicRole>('passenger')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await register.mutateAsync({ username, password, role })
      await login.mutateAsync({ username, password })
    } catch {
      // Errors are shown from the mutation state below.
    }
  }

  const pending = register.isPending || login.isPending

  return (
    <AuthLayout title="Регистрация" description="Выберите роль и придумайте логин">
      <form className="grid gap-4" onSubmit={submit}>
        <Tabs value={role} onValueChange={(value) => setRole(value as PublicRole)}>
          <TabsList className="w-full">
            <TabsTrigger value="passenger">Пассажир</TabsTrigger>
            <TabsTrigger value="driver">Водитель</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="grid gap-2">
          <Label htmlFor="username">Имя пользователя</Label>
          <Input
            id="username"
            autoComplete="username"
            required
            pattern="[A-Za-z0-9_]{3,32}"
            title="3–32 символа: латинские буквы, цифры, _"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="password">Пароль</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={10}
            maxLength={128}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">Не короче 10 символов.</p>
        </div>
        <ErrorAlert error={register.error ?? login.error} />
        <Button type="submit" disabled={pending}>Зарегистрироваться</Button>
        <p className="text-center text-sm text-muted-foreground">
          Уже есть аккаунт? <Link to="/login" className="text-foreground underline underline-offset-4">Войти</Link>
        </p>
      </form>
    </AuthLayout>
  )
}

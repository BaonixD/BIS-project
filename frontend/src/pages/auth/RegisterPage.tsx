import { t, useLocale } from '@/i18n/core'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { ArrowLeft, Car, Lock, User, type LucideIcon } from 'lucide-react'
import type { RegisterRequest } from '@/api'
import { useSession } from '@/auth/use-session'
import { Button, Input, showToast } from '@/components/ui-kit'
import { cn } from '@/lib/utils'
import { AuthHeading, AuthLayout, FormError } from './AuthLayout'
type PublicRole = RegisterRequest['role']
const ROLES = (): {
  role: PublicRole
  title: string
  subtitle: string
  icon: LucideIcon
}[] => [
  { role: 'passenger', title: t('Пассажир'), subtitle: t('Заказывать поездки'), icon: User },
  { role: 'driver', title: t('Водитель'), subtitle: t('Принимать заказы'), icon: Car },
]
/** Figma «RolePicker» 4:61: two cards; the selected one is black. */
function RolePicker({
  value,
  onChange,
}: {
  value: PublicRole
  onChange: (role: PublicRole) => void
}) {
  useLocale()
  return (
    <div role="radiogroup" aria-label={t('Роль')} className="flex w-full items-start gap-3">
      {ROLES().map(({ role, title, subtitle, icon: Icon }) => {
        const selected = role === value
        return (
          <button
            key={role}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(role)}
            className={cn(
              'flex min-w-0 flex-1 flex-col items-start gap-3 overflow-hidden rounded-lg p-4 text-left',
              'outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-bg-inverse focus-visible:ring-offset-2',
              selected ? 'bg-bg-inverse text-text-inverse' : 'bg-bg-subtle text-text-primary',
            )}
          >
            <Icon className="size-6" strokeWidth={2} aria-hidden />
            <span className="w-full text-headline">{title}</span>
            <span
              className={cn(
                'w-full text-caption',
                selected ? 'text-text-inverse' : 'text-text-secondary',
              )}
            >
              {subtitle}
            </span>
          </button>
        )
      })}
    </div>
  )
}
/** Figma «Auth / Register» 4:43. Registration does not sign in: the user continues on the login screen. */
export function RegisterPage() {
  useLocale()
  const { register } = useSession()
  const navigate = useNavigate()
  const [role, setRole] = useState<PublicRole>('passenger')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await register.mutateAsync({ username, password, role })
    } catch {
      return
    }
    showToast({ title: t('Аккаунт создан'), description: t('Войдите с этим именем и паролем') })
    navigate('/login', { state: { username } })
  }
  return (
    <AuthLayout top="register">
      <Link
        to="/login"
        aria-label={t('Назад ко входу')}
        className="-m-2.5 self-start rounded-full p-2.5 outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse"
      >
        <ArrowLeft className="size-6" strokeWidth={2} aria-hidden />
      </Link>
      <AuthHeading
        title={t('Создать аккаунт')}
        subtitle={t('Выберите, как будете пользоваться BIS')}
      />
      <RolePicker value={role} onChange={setRole} />
      <form className="flex flex-col gap-6" onSubmit={submit}>
        <div className="flex flex-col gap-3">
          <Input
            icon={User}
            name="username"
            placeholder={t('Имя пользователя')}
            autoComplete="username"
            autoCapitalize="none"
            required
            pattern="[A-Za-z0-9_]{3,32}"
            title={t('3–32 символа: латинские буквы, цифры, _')}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
          <Input
            icon={Lock}
            name="password"
            type="password"
            placeholder={t('Пароль — от 10 символов')}
            autoComplete="new-password"
            required
            minLength={10}
            maxLength={128}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <FormError error={register.error} />
        </div>
        <Button type="submit" className="w-full" loading={register.isPending}>
          {t('Создать аккаунт')}
        </Button>
      </form>
      <p className="text-caption text-text-tertiary">
        {t('Регистрация не выполняет вход — после неё войдите с этим именем и паролем.')}
      </p>
    </AuthLayout>
  )
}

import { t, useLocale } from '@/i18n/core'
import { LogOut } from 'lucide-react'
import { useSession } from '@/auth/use-session'
import { Button } from '@/components/ui/button'
export function LogoutButton() {
  useLocale()
  const { logout } = useSession()
  return (
    <Button variant="outline" disabled={logout.isPending} onClick={() => logout.mutate()}>
      <LogOut />
      {t(' Выйти')}
    </Button>
  )
}

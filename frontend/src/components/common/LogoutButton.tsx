import { LogOut } from 'lucide-react'
import { useSession } from '@/auth/use-session'
import { Button } from '@/components/ui/button'

export function LogoutButton() {
  const { logout } = useSession()
  return (
    <Button variant="outline" disabled={logout.isPending} onClick={() => logout.mutate()}>
      <LogOut /> Выйти
    </Button>
  )
}

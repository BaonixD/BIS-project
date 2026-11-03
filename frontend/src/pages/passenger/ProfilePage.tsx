import { useState, type FormEvent } from 'react'
import type { MyProfile } from '@/api'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { LogoutButton } from '@/components/common/LogoutButton'
import { PageHeader } from '@/components/common/PageHeader'
import { PageContainer } from '@/components/layout/PageContainer'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { useMyProfile, useUpdateMyProfile } from '@/hooks/use-profile'

function ProfileForm({ profile }: { profile: MyProfile }) {
  const update = useUpdateMyProfile()
  const [displayName, setDisplayName] = useState(profile.display_name ?? '')
  const [phone, setPhone] = useState(profile.phone ?? '')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    update.mutate({
      ...(displayName.trim() && { display_name: displayName.trim() }),
      ...(phone.trim() && { phone: phone.trim() }),
    })
  }

  return (
    <form className="grid gap-4" onSubmit={submit}>
      <p className="text-sm text-muted-foreground">Логин: {profile.username}</p>
      <div className="grid gap-2">
        <Label htmlFor="display_name">Имя</Label>
        <Input id="display_name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="phone">Телефон</Label>
        <Input id="phone" type="tel" placeholder="+7…" value={phone} onChange={(e) => setPhone(e.target.value)} />
      </div>
      <ErrorAlert error={update.error} />
      {update.isSuccess && <p className="text-sm text-muted-foreground">Сохранено</p>}
      <Button type="submit" disabled={update.isPending}>Сохранить</Button>
    </form>
  )
}

export function ProfilePage() {
  const profile = useMyProfile()
  return (
    <PageContainer>
      <PageHeader title="Профиль" action={<LogoutButton />} />
      <Card>
        <CardContent>
          {profile.isPending && <Skeleton className="h-40" />}
          {profile.isError && <ErrorAlert error={profile.error} />}
          {profile.data && <ProfileForm profile={profile.data} />}
        </CardContent>
      </Card>
    </PageContainer>
  )
}

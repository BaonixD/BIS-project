import { useState, type ComponentProps, type FormEvent } from 'react'
import type { Driver, DriverProfileUpdate } from '@/api'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { LogoutButton } from '@/components/common/LogoutButton'
import { PageHeader } from '@/components/common/PageHeader'
import { PageContainer } from '@/components/layout/PageContainer'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { useDriverProfile, useUpdateDriverProfile } from '@/hooks/use-driver'
import { APPROVAL_STATUS_LABELS, DRIVER_FIELD_LABELS } from '@/lib/labels'

const FIELDS = {
  full_name: 'ФИО',
  phone: 'Телефон',
  license_number: 'Номер водительских прав',
  make: 'Марка',
  model: 'Модель',
  color: 'Цвет',
  plate_number: 'Госномер',
  year: 'Год выпуска',
} as const

type FieldName = keyof typeof FIELDS
type FormState = Record<FieldName, string>

function initialState(driver: Driver): FormState {
  const v = driver.vehicle
  return {
    full_name: driver.full_name ?? '',
    phone: driver.phone ?? '',
    license_number: driver.license_number ?? '',
    make: v?.make ?? '',
    model: v?.model ?? '',
    color: v?.color ?? '',
    plate_number: v?.plate_number ?? '',
    year: v ? String(v.year) : '',
  }
}

/** PATCH semantics: empty fields are omitted (null is rejected); the vehicle is sent only when complete. */
function toUpdate(form: FormState): DriverProfileUpdate {
  const text = (value: string) => value.trim() || undefined
  const vehicleComplete = (['make', 'model', 'color', 'plate_number', 'year'] as const).every((f) => form[f].trim())
  return {
    full_name: text(form.full_name),
    phone: text(form.phone),
    license_number: text(form.license_number),
    vehicle: vehicleComplete
      ? {
          make: form.make.trim(),
          model: form.model.trim(),
          color: form.color.trim(),
          plate_number: form.plate_number.trim(),
          year: Number(form.year),
        }
      : undefined,
  }
}

function DriverProfileForm({ driver }: { driver: Driver }) {
  const update = useUpdateDriverProfile()
  const [form, setForm] = useState(() => initialState(driver))

  const field = (name: FieldName, props: ComponentProps<typeof Input> = {}) => (
    <div className="grid gap-2">
      <Label htmlFor={name}>{FIELDS[name]}</Label>
      <Input id={name} value={form[name]} onChange={(e) => setForm({ ...form, [name]: e.target.value })} {...props} />
    </div>
  )

  const submit = (event: FormEvent) => {
    event.preventDefault()
    update.mutate(toUpdate(form))
  }

  return (
    <form className="grid gap-4" onSubmit={submit}>
      {field('full_name', { autoComplete: 'name' })}
      {field('phone', { type: 'tel', placeholder: '+7…' })}
      {field('license_number')}
      <Separator />
      <p className="text-sm font-medium">Автомобиль</p>
      <div className="grid grid-cols-2 gap-3">
        {field('make')}
        {field('model')}
        {field('color')}
        {field('year', { type: 'number', min: 1980, inputMode: 'numeric' })}
      </div>
      {field('plate_number')}
      <ErrorAlert error={update.error} />
      {update.isSuccess && <p className="text-sm text-muted-foreground">Сохранено</p>}
      <Button type="submit" disabled={update.isPending}>Сохранить</Button>
    </form>
  )
}

export function DriverProfilePage() {
  const driver = useDriverProfile()
  return (
    <PageContainer>
      <PageHeader title="Профиль водителя" action={<LogoutButton />} />
      {driver.isPending && <Skeleton className="h-96" />}
      {driver.isError && <ErrorAlert error={driver.error} />}
      {driver.data && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Статус допуска
              <Badge variant={driver.data.approval_status === 'approved' ? 'default' : 'secondary'}>
                {APPROVAL_STATUS_LABELS[driver.data.approval_status]}
              </Badge>
            </CardTitle>
            {driver.data.missing_fields.length > 0 && (
              <p className="text-sm text-muted-foreground">
                Не заполнено: {driver.data.missing_fields.map((f) => DRIVER_FIELD_LABELS[f] ?? f).join(', ')}
              </p>
            )}
          </CardHeader>
          <CardContent>
            <DriverProfileForm driver={driver.data} />
          </CardContent>
        </Card>
      )}
    </PageContainer>
  )
}

import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { Calendar, Car, CreditCard, Phone, ShieldCheck, User } from 'lucide-react'
import { errorMessage, missingFields } from '@/api'
import type { NextDriver } from '@/api/driver-types'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { FullScreenLoader } from '@/components/common/FullScreenLoader'
import { BackHeader } from '@/components/driver/BackHeader'
import { Screen, ScreenColumn, ScreenFooter } from '@/components/driver/Screen'
import { SettingsField } from '@/components/driver/SettingsField'
import { Button, showToast } from '@/components/ui-kit'
import { useDriverProfile, useUpdateDriverProfile } from '@/hooks/use-driver'
import { DRIVER_FIELD_LABELS } from '@/lib/labels'
import { settingsForm, settingsUpdate, type SettingsForm } from './settings-form'

const FORM_ID = 'driver-settings'

function SectionLabel({ children }: { children: string }) {
  return <h2 className="w-full text-label text-text-tertiary">{children}</h2>
}

function SettingsFormView({ driver }: { driver: NextDriver }) {
  const navigate = useNavigate()
  const update = useUpdateDriverProfile()
  const [form, setForm] = useState(() => settingsForm(driver))
  const bind = (name: keyof SettingsForm) => ({
    name,
    value: form[name],
    onChange: (event: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [name]: event.target.value }),
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    update.mutate(settingsUpdate(form), {
      onSuccess: () => {
        showToast({ title: 'Сохранено' })
        navigate('/driver/profile')
      },
      onError: (error) => {
        const fields = missingFields(error).map((field) => DRIVER_FIELD_LABELS[field] ?? field)
        showToast({ title: errorMessage(error), description: fields.length ? `Не заполнено: ${fields.join(', ')}` : undefined })
      },
    })
  }

  return (
    <>
      <form id={FORM_ID} onSubmit={submit} className="flex w-full flex-col gap-4">
        <SectionLabel>ВОДИТЕЛЬ</SectionLabel>
        <div className="flex w-full flex-col gap-2.5">
          <SettingsField icon={User} aria-label="ФИО" placeholder="ФИО" autoComplete="name" {...bind('full_name')} />
          <SettingsField icon={Phone} aria-label="Телефон" placeholder="+7 7xx xxx xx xx" type="tel" autoComplete="tel" {...bind('phone')} />
          <SettingsField icon={CreditCard} prefix="Права" aria-label="Номер прав" placeholder="KZ 00000000" {...bind('license_number')} />
        </div>
        <SectionLabel>АВТОМОБИЛЬ</SectionLabel>
        <div className="flex w-full flex-col gap-2.5">
          <SettingsField icon={Car} aria-label="Марка и модель" placeholder="Марка и модель" {...bind('car')} />
          <SettingsField icon={Car} aria-label="Цвет" placeholder="Цвет" {...bind('color')} />
          <SettingsField icon={CreditCard} aria-label="Госномер" placeholder="Госномер" {...bind('plate_number')} />
          {!driver.vehicle && (
            <SettingsField icon={Calendar} aria-label="Год выпуска" placeholder="Год выпуска" inputMode="numeric" {...bind('year')} />
          )}
        </div>
        <div className="flex w-full items-center gap-2.5 overflow-hidden rounded-md bg-bg-subtle p-3">
          <ShieldCheck className="size-6 shrink-0 text-text-primary" strokeWidth={2} aria-hidden />
          <p className="min-w-0 flex-1 text-caption text-text-secondary">
            Изменение ФИО или прав отправит профиль на повторную проверку
          </p>
        </div>
      </form>
      <ScreenFooter>
        <Button type="submit" form={FORM_ID} className="w-full" loading={update.isPending}>
          Сохранить
        </Button>
      </ScreenFooter>
    </>
  )
}

/** Figma 26:500: driver and vehicle settings. */
export function DriverSettingsPage() {
  const driver = useDriverProfile()
  if (driver.isPending) return <FullScreenLoader />
  return (
    <Screen overNav>
      <ScreenColumn className="gap-4 pt-[calc(9px+env(safe-area-inset-top))] pb-32">
        <BackHeader title="Настройки" fallback="/driver/profile" />
        <ErrorAlert error={driver.error} />
        {driver.data && <SettingsFormView driver={driver.data} />}
      </ScreenColumn>
    </Screen>
  )
}

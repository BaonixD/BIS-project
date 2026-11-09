import { useState } from 'react'
import { Dialog } from 'radix-ui'
import { Check } from 'lucide-react'
import { TARIFF_LABELS, TARIFFS, type Tariff } from '@/api/driver-types'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Button, CarIcon } from '@/components/ui-kit'
import { cn } from '@/lib/utils'

export function DriverCategoriesSheet({
  available,
  initial,
  busy,
  error,
  online,
  onConfirm,
  onClose,
}: {
  available: readonly Tariff[]
  initial: readonly Tariff[]
  busy: boolean
  error: Error | null
  online: boolean
  onConfirm: (categories: Tariff[]) => void
  onClose: () => void
}) {
  const allowed = TARIFFS.filter((tariff) => available.includes(tariff))
  const [selected, setSelected] = useState<readonly Tariff[]>(() =>
    initial.filter((tariff) => allowed.includes(tariff)),
  )
  const categories = allowed.filter((tariff) => selected.includes(tariff))
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose()
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <Dialog.Content className="fixed inset-x-0 bottom-0 z-50 flex max-h-[90dvh] flex-col gap-4 overflow-y-auto rounded-t-xl bg-bg-canvas px-4 pt-6 pb-[calc(24px+env(safe-area-inset-bottom))] shadow-sheet outline-none sm:inset-x-auto sm:top-1/2 sm:bottom-auto sm:left-1/2 sm:w-[420px] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-xl sm:p-6">
          <Dialog.Title className="text-title text-text-primary">Тарифы смены</Dialog.Title>
          <Dialog.Description className="text-callout text-text-secondary">
            Отметьте, какие заказы хотите получать. Доступны тарифы класса вашей машины и ниже.
          </Dialog.Description>
          <fieldset disabled={busy} className="flex flex-col gap-2">
            <legend className="sr-only">Принимать заказы</legend>
            {allowed.map((tariff) => {
              const checked = categories.includes(tariff)
              return (
                <label
                  key={tariff}
                  className={cn(
                    'relative flex min-h-16 cursor-pointer items-center gap-3 rounded-md border-2 px-4 py-3 transition-colors focus-within:ring-2 focus-within:ring-bg-inverse focus-within:ring-offset-2',
                    checked
                      ? 'border-bg-inverse bg-bg-subtle'
                      : 'border-border-default bg-bg-canvas',
                    busy && 'cursor-default opacity-50',
                  )}
                >
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={checked}
                    onChange={(event) =>
                      setSelected(
                        event.target.checked
                          ? [...categories, tariff]
                          : categories.filter((value) => value !== tariff),
                      )
                    }
                  />
                  <CarIcon carClass={tariff} />
                  <span className="flex-1 text-body-medium text-text-primary">
                    {TARIFF_LABELS[tariff]}
                  </span>
                  <span
                    aria-hidden
                    className={cn(
                      'flex size-6 shrink-0 items-center justify-center rounded-[6px] border',
                      checked
                        ? 'border-bg-inverse bg-bg-inverse text-text-inverse'
                        : 'border-border-default bg-bg-canvas',
                    )}
                  >
                    {checked && <Check className="size-4" strokeWidth={2.5} />}
                  </span>
                </label>
              )
            })}
          </fieldset>
          <p
            className={cn(
              'text-caption',
              categories.length ? 'text-text-secondary' : 'text-accent-danger',
            )}
            role="status"
          >
            {categories.length
              ? `Выбрано тарифов: ${categories.length}`
              : 'Выберите хотя бы один тариф'}
          </p>
          <ErrorAlert error={error} />
          <Button
            className="w-full"
            disabled={categories.length === 0}
            loading={busy}
            onClick={() => onConfirm(categories)}
          >
            {online ? 'Сохранить тарифы' : 'Выйти на линию'}
          </Button>
          <Button variant="ghost" size="md" className="w-full" disabled={busy} onClick={onClose}>
            Отмена
          </Button>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

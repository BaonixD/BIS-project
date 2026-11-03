import { useState } from 'react'
import { Check } from 'lucide-react'
import { TARIFF_LABELS, TARIFFS, type Tariff } from '@/api/driver-types'
import { BottomSheet, Button, CarIcon } from '@/components/ui-kit'
import { cn } from '@/lib/utils'

/** Approve a driver (or change the class) with the class of the car: it serves its tariff and the lower ones. */
export function CarClassSheet({
  initial,
  confirmLabel,
  busy,
  onConfirm,
  onClose,
}: {
  initial: Tariff
  confirmLabel: string
  busy: boolean
  onConfirm: (carClass: Tariff) => void
  onClose: () => void
}) {
  const [value, setValue] = useState<Tariff>(initial)
  return (
    <div className="fixed inset-0 z-50 lg:top-(--top-bar-height)">
      <div aria-hidden className="absolute inset-0 bg-black/40" onClick={onClose} />
      <BottomSheet role="dialog" aria-modal aria-label="Класс машины" className="bottom-0 pb-7">
        <h2 className="w-full text-title text-text-primary">Класс машины</h2>
        <p className="w-full text-callout text-text-secondary">
          Водитель получит заказы этого тарифа и тарифов ниже.
        </p>
        <div role="radiogroup" aria-label="Класс машины" className="flex w-full flex-col gap-2">
          {TARIFFS.map((tariff) => {
            const selected = tariff === value
            return (
              <button
                key={tariff}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setValue(tariff)}
                className={cn(
                  'flex h-16 w-full items-center gap-3 rounded-md border-solid px-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse',
                  selected ? 'border-2 border-bg-inverse bg-bg-subtle' : 'border border-border-default bg-bg-canvas',
                )}
              >
                <CarIcon carClass={tariff} />
                <span className="flex-1 text-body-medium text-text-primary">{TARIFF_LABELS[tariff]}</span>
                {selected && <Check className="size-5 text-text-primary" strokeWidth={2.5} aria-hidden />}
              </button>
            )
          })}
        </div>
        <Button className="w-full" loading={busy} onClick={() => onConfirm(value)}>
          {confirmLabel}
        </Button>
        <Button variant="ghost" size="md" className="w-full" onClick={onClose}>
          Отмена
        </Button>
      </BottomSheet>
    </div>
  )
}

import type { ComponentProps } from 'react'
import { Banknote, CreditCard } from 'lucide-react'
import type { PaymentMethod } from '@/api'
import { cn } from '@/lib/utils'

const METHOD = {
  cash: { icon: Banknote, title: 'Наличные', subtitle: 'водителю', iconBox: 'bg-bg-muted text-text-primary' },
  kaspi_link: { icon: CreditCard, title: 'Kaspi', subtitle: 'при назначении', iconBox: 'bg-accent-kaspi text-text-inverse' },
} satisfies Record<PaymentMethod, unknown>

interface PaymentMethodCardProps extends Omit<ComponentProps<'button'>, 'title'> {
  method: PaymentMethod
  selected?: boolean
  title?: string
  subtitle?: string
}

/** Figma «PaymentSelector» 12:545 item: 52px tall, radius 12, 28px icon tile; selected — white with a 1.5px black border. */
export function PaymentMethodCard({
  method,
  selected = false,
  title,
  subtitle,
  className,
  type = 'button',
  ...props
}: PaymentMethodCardProps) {
  const { icon: Icon, iconBox, ...text } = METHOD[method]
  return (
    <button
      type={type}
      role="radio"
      aria-checked={selected}
      data-slot="payment-method-card"
      className={cn(
        'flex h-[52px] min-w-0 flex-1 items-center gap-2 overflow-hidden rounded-md border-[1.5px] border-solid px-2.5 text-left',
        'outline-none transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-bg-inverse focus-visible:ring-offset-2',
        selected ? 'border-bg-inverse bg-bg-canvas' : 'border-bg-subtle bg-bg-subtle',
        className,
      )}
      {...props}
    >
      <span className={cn('flex size-7 shrink-0 items-center justify-center rounded-[7px]', iconBox)}>
        <Icon className="size-4" strokeWidth={2} aria-hidden />
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="truncate text-[14px] leading-[18px] font-medium text-text-primary">{title ?? text.title}</span>
        <span className="truncate text-[12px] leading-4 text-text-secondary">{subtitle ?? text.subtitle}</span>
      </span>
    </button>
  )
}

/** Cash / Kaspi pair, 8px apart. */
export function PaymentMethodPicker({
  value,
  onChange,
  className,
}: {
  value: PaymentMethod
  onChange: (method: PaymentMethod) => void
  className?: string
}) {
  return (
    <div role="radiogroup" aria-label="Способ оплаты" className={cn('flex w-full items-center gap-2', className)}>
      {(['cash', 'kaspi_link'] as const).map((method) => (
        <PaymentMethodCard key={method} method={method} selected={value === method} onClick={() => onChange(method)} />
      ))}
    </div>
  )
}

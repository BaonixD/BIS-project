import type { ComponentProps } from 'react'
import carImage from '@/assets/car.png'
import { cn } from '@/lib/utils'

interface TariffCardProps extends Omit<ComponentProps<'button'>, 'children'> {
  name: string
  price: string
  selected?: boolean
}

/**
 * Figma «TariffCard» 21:81: 212×80, radius 10; Selected — subtle background with a 2px black border,
 * Default — white with a 1px border and a 45% car. `mix-blend-multiply` drops the render's white background.
 */
export function TariffCard({ name, price, selected = false, className, type = 'button', ...props }: TariffCardProps) {
  return (
    <button
      type={type}
      role="radio"
      aria-checked={selected}
      data-slot="tariff-card"
      className={cn(
        'flex h-20 w-[212px] shrink-0 snap-start items-center gap-1 overflow-hidden rounded-[10px] border-solid pr-1 pl-3.5 text-left',
        'outline-none transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-bg-inverse focus-visible:ring-offset-2',
        selected ? 'border-2 border-text-primary bg-bg-subtle' : 'border border-border-default bg-bg-canvas',
        className,
      )}
      {...props}
    >
      <span className="flex min-w-0 flex-1 flex-col items-start gap-0.5 whitespace-nowrap">
        <span className="text-[22px] leading-[30px] font-medium tracking-[-0.3px] text-text-primary">{price}</span>
        <span className="text-[15px] leading-5 text-text-secondary">{name}</span>
      </span>
      <img
        src={carImage}
        alt=""
        draggable={false}
        className={cn(
          'pointer-events-none h-[72px] w-[108px] shrink-0 object-cover mix-blend-multiply transition-opacity duration-150',
          !selected && 'opacity-45',
        )}
      />
    </button>
  )
}

export interface TariffOption {
  id: string
  name: string
  price: string
}

interface TariffCarouselProps {
  options: TariffOption[]
  value: string | null
  onChange: (id: string) => void
  label?: string
  className?: string
}

/** Horizontal tariff strip (Figma «Tariffs» 21:682): 10px gap, scroll-snap, bleeds to the sheet edges on mobile. */
export function TariffCarousel({ options, value, onChange, label = 'Тариф', className }: TariffCarouselProps) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        '-mx-4 flex snap-x snap-mandatory scroll-px-4 gap-2.5 overflow-x-auto px-4 scrollbar-none lg:-mx-6 lg:scroll-px-6 lg:px-6',
        className,
      )}
    >
      {options.map((option) => (
        <TariffCard
          key={option.id}
          name={option.name}
          price={option.price}
          selected={option.id === value}
          onClick={() => onChange(option.id)}
        />
      ))}
    </div>
  )
}

import { t, useLocale } from '@/i18n/core'
import { useEffect, useRef, useState, type ComponentProps } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import carImage from '@/assets/car.png'
import { cn } from '@/lib/utils'
interface TariffCardProps extends Omit<ComponentProps<'button'>, 'children'> {
  name: string
  price: string
  selected?: boolean
}
/**
 * Figma «TariffCard» 21:81: 176×64, radius 10; Selected — subtle background with a 1.5px black border,
 * Default — white with a 1px border and a 45% car. `mix-blend-multiply` drops the render's white background.
 */
export function TariffCard({
  name,
  price,
  selected = false,
  className,
  type = 'button',
  ...props
}: TariffCardProps) {
  useLocale()
  return (
    <button
      type={type}
      role="radio"
      aria-checked={selected}
      data-slot="tariff-card"
      className={cn(
        'flex h-16 w-[176px] shrink-0 snap-start items-center gap-1 overflow-hidden rounded-[10px] border-solid pr-1 pl-3 text-left',
        'outline-none transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-bg-inverse focus-visible:ring-offset-2',
        selected
          ? 'border-[1.5px] border-text-primary bg-bg-subtle'
          : 'border border-border-default bg-bg-canvas',
        className,
      )}
      {...props}
    >
      <span className="flex min-w-0 flex-1 flex-col items-start gap-0.5 whitespace-nowrap">
        <span className="text-[18px] leading-6 font-medium tracking-[-0.2px] text-text-primary">
          {price}
        </span>
        <span className="text-[13px] leading-[18px] text-text-secondary">{name}</span>
      </span>
      <img
        src={carImage}
        alt=""
        draggable={false}
        className={cn(
          'pointer-events-none h-[58px] w-[86px] shrink-0 object-cover mix-blend-multiply transition-opacity duration-150',
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
export function TariffCarousel({
  options,
  value,
  onChange,
  label = t('Тариф'),
  className,
}: TariffCarouselProps) {
  useLocale()
  const strip = useRef<HTMLDivElement>(null)
  const [edges, setEdges] = useState({ start: true, end: false })
  useEffect(() => {
    const node = strip.current
    if (!node) return
    const update = () =>
      setEdges({
        start: node.scrollLeft <= 1,
        end: node.scrollLeft + node.clientWidth >= node.scrollWidth - 1,
      })
    update()
    const observer = new ResizeObserver(update)
    observer.observe(node)
    node.addEventListener('scroll', update, { passive: true })
    return () => {
      observer.disconnect()
      node.removeEventListener('scroll', update)
    }
  }, [options.length])
  const scroll = (direction: number) => {
    const node = strip.current
    if (!node) return
    node.scrollBy({
      left: direction * Math.max(176, node.clientWidth - 24),
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
        ? 'instant'
        : 'smooth',
    })
  }
  return (
    <div className={cn('flex w-full min-w-0 flex-col gap-2', className)}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-caption text-text-secondary">{label}</p>
        <div className="flex gap-1">
          {([-1, 1] as const).map((direction) => (
            <button
              key={direction}
              type="button"
              aria-label={t(direction < 0 ? 'Предыдущие тарифы' : 'Следующие тарифы')}
              disabled={direction < 0 ? edges.start : edges.end}
              onClick={() => scroll(direction)}
              className="flex size-9 items-center justify-center rounded-full bg-bg-subtle text-text-primary outline-none focus-visible:ring-2 focus-visible:ring-bg-inverse disabled:opacity-30"
            >
              {direction < 0 ? (
                <ChevronLeft className="size-5" aria-hidden />
              ) : (
                <ChevronRight className="size-5" aria-hidden />
              )}
            </button>
          ))}
        </div>
      </div>
      <div
        ref={strip}
        role="radiogroup"
        aria-label={label}
        className="flex w-full min-w-0 snap-x snap-mandatory gap-2.5 overflow-x-auto overscroll-x-contain px-0.5 py-1 scrollbar-none"
        onKeyDown={(event) => {
          const current = options.findIndex((option) => option.id === value)
          let next: number
          if (event.key === 'ArrowRight') next = (current + 1) % options.length
          else if (event.key === 'ArrowLeft') next = (current - 1 + options.length) % options.length
          else if (event.key === 'Home') next = 0
          else if (event.key === 'End') next = options.length - 1
          else return
          const option = options[next]
          if (!option) return
          event.preventDefault()
          onChange(option.id)
          strip.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[next]?.focus()
        }}
      >
        {options.map((option) => (
          <TariffCard
            key={option.id}
            name={option.name}
            price={option.price}
            selected={option.id === value}
            tabIndex={option.id === value || (!value && option === options[0]) ? 0 : -1}
            onClick={() => onChange(option.id)}
            onFocus={(event) =>
              event.currentTarget.scrollIntoView?.({ block: 'nearest', inline: 'nearest' })
            }
          />
        ))}
      </div>
    </div>
  )
}

import business from '@/assets/car-icons/business.svg'
import comfortPlus from '@/assets/car-icons/comfort-plus.svg'
import comfort from '@/assets/car-icons/comfort.svg'
import economy from '@/assets/car-icons/economy.svg'
import { cn } from '@/lib/utils'

export type CarClass = 'economy' | 'comfort' | 'comfort_plus' | 'business'

const SOURCES: Record<CarClass, string> = {
  economy,
  comfort,
  comfort_plus: comfortPlus,
  business,
}

/** Figma «CarIcon/*» 20:63–20:93: black car silhouettes, 60×28 (72×33.6 in DriverCard). */
export function CarIcon({ carClass = 'comfort', className }: { carClass?: CarClass; className?: string }) {
  return (
    <img
      src={SOURCES[carClass]}
      alt=""
      draggable={false}
      data-slot="car-icon"
      className={cn('block h-7 w-[60px] shrink-0', className)}
    />
  )
}

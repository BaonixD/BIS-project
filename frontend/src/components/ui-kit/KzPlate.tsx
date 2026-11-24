import { t, useLocale } from '@/i18n/core'
import { cn } from '@/lib/utils'
import { parseKzPlate } from './kz-plate'

/** The flag at plate size: sky field, gold sun and the ornament strip at the hoist. */
function PlateFlag() {
  return (
    <svg viewBox="0 0 20 10" className="h-[7px] w-3.5" aria-hidden>
      <rect width="20" height="10" fill="#00afca" />
      <rect x="1" width="1.3" height="10" fill="#fec50c" />
      <circle cx="11" cy="4.6" r="2.3" fill="#fec50c" />
      <path d="M8 7.4h6" stroke="#fec50c" strokeWidth="0.8" strokeLinecap="round" />
    </svg>
  )
}

/**
 * A Kazakhstan plate as on the street (2012 standard): flag and «KZ» on the left, «123 ABC»,
 * then the region (02 = Almaty) behind a divider. Other formats stay a plain badge.
 */
export function KzPlate({ plate, className }: { plate: string; className?: string }) {
  useLocale()
  const parts = parseKzPlate(plate)
  if (!parts)
    return (
      <span
        className={cn(
          'rounded-[6px] border-[1.5px] border-solid border-bg-inverse bg-bg-canvas px-2 py-1 text-[12px] leading-4 font-bold tracking-[0.2px] whitespace-nowrap text-text-primary',
          className,
        )}
      >
        {plate}
      </span>
    )
  const spoken = `${parts.digits} ${parts.letters} ${parts.region}`
  return (
    <span
      role="img"
      aria-label={t('Госномер {p0}', { p0: spoken })}
      className={cn(
        'inline-flex h-7 shrink-0 items-stretch overflow-hidden rounded-[5px] border-[1.5px] border-solid border-[#111] bg-white leading-none font-bold whitespace-nowrap text-[#111] shadow-[inset_0_0_0_1px_#fff]',
        className,
      )}
    >
      <span aria-hidden className="flex flex-col items-center justify-center gap-[2px] pr-[3px] pl-1">
        <PlateFlag />
        <span className="text-[7px] tracking-[0.02em]">KZ</span>
      </span>
      <span aria-hidden className="flex items-center px-1 text-[15px] tracking-[0.06em] tabular-nums">
        {parts.digits}
        <span className="ml-1">{parts.letters}</span>
      </span>
      <span
        aria-hidden
        className="flex items-center border-l-[1.5px] border-solid border-[#111] px-1.5 text-[15px] tabular-nums"
      >
        {parts.region}
      </span>
    </span>
  )
}

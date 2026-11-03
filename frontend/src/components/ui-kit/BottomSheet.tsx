import { useEffect, useRef, type ComponentProps, type ReactNode } from 'react'
import { motion } from 'motion/react'
import { cn } from '@/lib/utils'

interface BottomSheetProps extends Omit<ComponentProps<'section'>, 'children'> {
  children: ReactNode
  /** Centre the grabber and content (status sheets: «Водитель найден», «Отменить поездку?»). */
  centered?: boolean
  /** Dim the map behind the sheet (modal states). */
  dimmed?: boolean
  /** Reports the rendered height, e.g. to pad Leaflet's fitBounds. */
  onHeightChange?: (height: number) => void
}

/**
 * Figma BottomSheet (4:174): white, 24px top corners, Elevation/Sheet, grabber 36×5, 16px gaps.
 * At ≥1024px it becomes the floating left panel of Desktop 7:2 (400px, radius 20, Elevation/Card).
 * Place it inside a `relative` map container; it runs under the bottom nav and `--sheet-offset` pads its content above it.
 */
export function BottomSheet({ children, centered, dimmed, onHeightChange, className, ...props }: BottomSheetProps) {
  const ref = useRef<HTMLElement>(null)

  useEffect(() => {
    const node = ref.current
    if (!node || !onHeightChange) return
    const observer = new ResizeObserver(() => onHeightChange(node.getBoundingClientRect().height))
    observer.observe(node)
    return () => observer.disconnect()
  }, [onHeightChange])

  return (
    <>
      {dimmed && (
        <motion.div
          data-slot="sheet-dim"
          aria-hidden
          className="absolute inset-0 z-10 bg-dim"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.2 }}
        />
      )}
      <motion.section
        ref={ref}
        data-slot="bottom-sheet"
        initial={{ opacity: 0, y: 48 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 420, damping: 38, mass: 0.9 }}
        className={cn(
          'absolute inset-x-0 bottom-0 z-20 flex max-h-[calc(100%-56px)] flex-col gap-4 overflow-y-auto',
          'rounded-t-xl bg-bg-canvas px-4 pt-2 pb-[calc(var(--sheet-offset)+20px)] shadow-sheet',
          'lg:top-8 lg:right-auto lg:bottom-auto lg:left-8 lg:max-h-[calc(100%-64px)] lg:w-[400px] lg:rounded-[20px] lg:p-6 lg:shadow-card',
          centered && 'items-center pb-[calc(var(--sheet-offset)+28px)] text-center',
          className,
        )}
        {...(props as ComponentProps<typeof motion.section>)}
      >
        <div
          data-slot="sheet-grabber"
          aria-hidden
          className="h-[5px] w-9 shrink-0 rounded-[3px] bg-bg-muted lg:hidden"
        />
        {children}
      </motion.section>
    </>
  )
}

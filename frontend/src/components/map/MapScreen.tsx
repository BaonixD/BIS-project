import type { ReactNode } from 'react'
import { BottomSheet } from '@/components/ui-kit'

/**
 * Full-screen map under the shell chrome with a bottom sheet
 * (a floating left panel at ≥1024px, as in Figma Desktop 7:2).
 */
export function MapScreen({
  map,
  sheet,
  sheetLabel = 'Панель заказа',
  onSheetHeightChange,
}: {
  map: ReactNode
  sheet: ReactNode
  sheetLabel?: string
  onSheetHeightChange?: (height: number) => void
}) {
  return (
    <div className="fixed inset-0 isolate lg:top-(--top-bar-height)">
      <div className="absolute inset-0 z-0">{map}</div>
      <BottomSheet aria-label={sheetLabel} onHeightChange={onSheetHeightChange}>
        {sheet}
      </BottomSheet>
    </div>
  )
}

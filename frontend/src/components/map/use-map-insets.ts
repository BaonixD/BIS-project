import { useEffect, useState } from 'react'
import type { MapInsets } from './layers'

const DESKTOP_QUERY = '(min-width: 1024px)'
/** Desktop panel: 32px from the left + 400px wide (Figma Desktop 7:2). */
const DESKTOP_PANEL_INSET = 32 + 400

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const media = window.matchMedia(query)
    const update = () => setMatches(media.matches)
    update()
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [query])
  return matches
}

/** Map padding for fitBounds: the sheet height on mobile, the floating panel on desktop. */
export function useMapInsets(sheetHeight: number): MapInsets {
  const desktop = useMediaQuery(DESKTOP_QUERY)
  return desktop ? { left: DESKTOP_PANEL_INSET } : { bottom: sheetHeight }
}

import { useEffect, useSyncExternalStore } from 'react'

// Order steps (Figma 4:253, 23:2, 23:97) have no bottom nav: their sheet reaches the screen edge.
let hiders = 0
const listeners = new Set<() => void>()

function emit() {
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function useBottomNavHidden(): boolean {
  return useSyncExternalStore(subscribe, () => hiders > 0)
}

export function useHideBottomNav(hidden: boolean) {
  useEffect(() => {
    if (!hidden) return
    hiders += 1
    emit()
    return () => {
      hiders -= 1
      emit()
    }
  }, [hidden])
}

import { Moon, Sun } from 'lucide-react'
import { t, useLocale } from '@/i18n/core'
import { setTheme, useDarkTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'

/** One tap between light and dark; the full choice (with «system») lives in the profile. */
export function ThemeToggle({ className }: { className?: string }) {
  useLocale()
  const dark = useDarkTheme()
  return (
    <button
      type="button"
      aria-label={dark ? t('Светлая тема') : t('Тёмная тема')}
      onClick={() => setTheme(dark ? 'light' : 'dark')}
      className={cn(
        'flex size-10 shrink-0 items-center justify-center rounded-full outline-none transition-colors focus-visible:ring-2 focus-visible:ring-bg-inverse',
        className,
      )}
    >
      {dark ? <Sun className="size-5" aria-hidden /> : <Moon className="size-5" aria-hidden />}
    </button>
  )
}

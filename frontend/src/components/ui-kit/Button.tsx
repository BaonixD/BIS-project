import type { ComponentProps } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { LoaderCircle } from 'lucide-react'
import { Slot } from 'radix-ui'
import { cn } from '@/lib/utils'

/** Figma «Button» 2:126: Type = Primary | Secondary | Ghost | Danger, Size = Large (56) | Medium (44). */
export const buttonVariants = cva(
  [
    'inline-flex shrink-0 items-center justify-center gap-2 rounded-md whitespace-nowrap select-none',
    'transition-[opacity,background-color] duration-150 outline-none',
    'focus-visible:ring-2 focus-visible:ring-bg-inverse focus-visible:ring-offset-2',
    'active:opacity-80 disabled:pointer-events-none disabled:opacity-40',
    "[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-5",
  ],
  {
    variants: {
      variant: {
        primary: 'bg-bg-inverse text-text-inverse',
        secondary: 'bg-bg-muted text-text-primary',
        ghost: 'bg-transparent text-text-primary',
        danger: 'bg-bg-subtle text-accent-danger',
      },
      size: {
        lg: 'h-14 px-5 text-body-medium',
        md: 'h-11 px-4 text-callout',
      },
    },
    defaultVariants: { variant: 'primary', size: 'lg' },
  },
)

export type ButtonVariant = NonNullable<VariantProps<typeof buttonVariants>['variant']>
export type ButtonSize = NonNullable<VariantProps<typeof buttonVariants>['size']>

export interface ButtonProps extends ComponentProps<'button'> {
  variant?: ButtonVariant
  size?: ButtonSize
  /** Shows a spinner and blocks clicks. */
  loading?: boolean
  /** Render the child element (e.g. a router Link) with button styles. */
  asChild?: boolean
}

export function Button({
  variant = 'primary',
  size = 'lg',
  loading = false,
  asChild = false,
  disabled,
  className,
  children,
  type,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot.Root : 'button'
  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      type={asChild ? undefined : (type ?? 'button')}
      disabled={asChild ? undefined : disabled || loading}
      aria-busy={loading || undefined}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    >
      {asChild ? (
        children
      ) : (
        <>
          {loading && <LoaderCircle className="animate-spin" aria-hidden />}
          {children}
        </>
      )}
    </Comp>
  )
}

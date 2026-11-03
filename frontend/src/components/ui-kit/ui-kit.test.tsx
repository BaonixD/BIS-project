import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import {
  BottomSheet,
  Button,
  Chip,
  RatingStars,
  StatusPill,
  Tag,
  TariffCard,
  TariffCarousel,
} from '@/components/ui-kit'

describe('Button', () => {
  it.each([
    ['primary', 'bg-bg-inverse'],
    ['secondary', 'bg-bg-muted'],
    ['ghost', 'bg-transparent'],
    ['danger', 'text-accent-danger'],
  ] as const)('renders the %s variant', (variant, expectedClass) => {
    render(<Button variant={variant}>Заказать</Button>)
    const button = screen.getByRole('button', { name: 'Заказать' })
    expect(button).toHaveAttribute('data-variant', variant)
    expect(button).toHaveClass(expectedClass)
  })

  it.each([
    ['lg', 'h-14'],
    ['md', 'h-11'],
  ] as const)('renders the %s size', (size, heightClass) => {
    render(<Button size={size}>Заказать</Button>)
    expect(screen.getByRole('button')).toHaveClass(heightClass)
  })

  it('defaults to primary large', () => {
    render(<Button>Заказать</Button>)
    const button = screen.getByRole('button')
    expect(button).toHaveAttribute('data-variant', 'primary')
    expect(button).toHaveAttribute('data-size', 'lg')
  })

  it('is disabled and busy while loading', () => {
    render(<Button loading>Заказать</Button>)
    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
  })
})

describe('StatusPill', () => {
  it('exposes its tone', () => {
    render(<StatusPill tone="success">Оплачено</StatusPill>)
    expect(screen.getByText('Оплачено')).toHaveAttribute('data-tone', 'success')
  })
})

describe('Chip', () => {
  it('reflects selection with aria-pressed and toggles on click', async () => {
    const onClick = vi.fn()
    const { rerender } = render(<Chip selected={false} onClick={onClick}>Все</Chip>)
    const chip = screen.getByRole('button', { name: 'Все' })
    expect(chip).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(chip)
    expect(onClick).toHaveBeenCalledOnce()
    rerender(<Chip selected onClick={onClick}>Все</Chip>)
    expect(chip).toHaveAttribute('aria-pressed', 'true')
  })
})

describe('Tag', () => {
  function Controlled() {
    const [selected, setSelected] = useState(false)
    return (
      <Tag selected={selected} onSelectedChange={setSelected}>
        Вежливый
      </Tag>
    )
  }

  it('shows a check only when selected', async () => {
    render(<Controlled />)
    const tag = screen.getByRole('button', { name: 'Вежливый' })
    expect(tag).toHaveAttribute('aria-pressed', 'false')
    expect(tag.querySelector('[data-slot="tag-check"]')).toBeNull()
    await userEvent.click(tag)
    expect(tag).toHaveAttribute('aria-pressed', 'true')
    expect(tag.querySelector('[data-slot="tag-check"]')).not.toBeNull()
  })
})

describe('RatingStars', () => {
  function Controlled({ onChange }: { onChange: (value: number) => void }) {
    const [value, setValue] = useState(0)
    return (
      <RatingStars
        value={value}
        onChange={(next) => {
          setValue(next)
          onChange(next)
        }}
      />
    )
  }

  it('sets the rating on click', async () => {
    const onChange = vi.fn()
    render(<Controlled onChange={onChange} />)
    await userEvent.click(screen.getByRole('radio', { name: '3 из 5' }))
    expect(onChange).toHaveBeenLastCalledWith(3)
    expect(screen.getByRole('radio', { name: '3 из 5' })).toHaveAttribute('aria-checked', 'true')
  })

  it('changes the rating with arrow, Home and End keys', async () => {
    const onChange = vi.fn()
    render(<Controlled onChange={onChange} />)
    await userEvent.click(screen.getByRole('radio', { name: '2 из 5' }))
    await userEvent.keyboard('{ArrowRight}')
    expect(onChange).toHaveBeenLastCalledWith(3)
    expect(screen.getByRole('radio', { name: '3 из 5' })).toHaveFocus()
    await userEvent.keyboard('{ArrowLeft}{ArrowLeft}')
    expect(onChange).toHaveBeenLastCalledWith(1)
    await userEvent.keyboard('{End}')
    expect(onChange).toHaveBeenLastCalledWith(5)
    await userEvent.keyboard('{Home}')
    expect(onChange).toHaveBeenLastCalledWith(1)
  })

  it('keeps a single tab stop', () => {
    render(<RatingStars value={4} onChange={() => {}} />)
    const tabbable = screen.getAllByRole('radio').filter((radio) => radio.tabIndex === 0)
    expect(tabbable).toHaveLength(1)
    expect(tabbable[0]).toHaveAccessibleName('4 из 5')
  })

  it('ignores input when read-only', async () => {
    const onChange = vi.fn()
    render(<RatingStars value={2} onChange={onChange} readOnly />)
    await userEvent.click(screen.getByRole('radio', { name: '5 из 5' }))
    expect(onChange).not.toHaveBeenCalled()
  })
})

describe('TariffCard', () => {
  it('marks the selected card', () => {
    render(<TariffCard name="Эконом" price="2 200 ₸" selected />)
    expect(screen.getByRole('radio', { name: /Эконом/ })).toHaveAttribute('aria-checked', 'true')
  })

  it('selects a tariff in the carousel', async () => {
    const onChange = vi.fn()
    render(
      <TariffCarousel
        value="economy"
        onChange={onChange}
        options={[
          { id: 'economy', name: 'Эконом', price: '2 200 ₸' },
          { id: 'comfort', name: 'Комфорт', price: '2 925 ₸' },
        ]}
      />,
    )
    expect(screen.getByRole('radiogroup', { name: 'Тариф' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Эконом/ })).toHaveAttribute('aria-checked', 'true')
    await userEvent.click(screen.getByRole('radio', { name: /Комфорт/ }))
    expect(onChange).toHaveBeenCalledWith('comfort')
  })
})

describe('BottomSheet', () => {
  it('renders its content in a labelled region with a grabber', () => {
    render(
      <BottomSheet aria-label="Заказ">
        <p>Куда едем?</p>
      </BottomSheet>,
    )
    const sheet = screen.getByRole('region', { name: 'Заказ' })
    expect(sheet).toHaveTextContent('Куда едем?')
    expect(sheet.querySelector('[data-slot="sheet-grabber"]')).not.toBeNull()
  })

  it('renders a dim overlay when modal', () => {
    const { container } = render(
      <BottomSheet aria-label="Отмена" dimmed>
        <p>Отменить поездку?</p>
      </BottomSheet>,
    )
    expect(container.querySelector('[data-slot="sheet-dim"]')).not.toBeNull()
  })
})

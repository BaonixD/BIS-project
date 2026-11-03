import { useEffect, useState, type ReactNode } from 'react'
import { ArrowLeft, Banknote, Car, Check, Clock, Locate, MapPin, Menu, Navigation, Receipt, Search, X } from 'lucide-react'
import type { PaymentMethod } from '@/api'
import { BottomNav } from '@/components/layout/BottomNav'
import { TopBar } from '@/components/layout/TopBar'
import { MapView } from '@/components/map/MapView'
import { useMapInsets } from '@/components/map/use-map-insets'
import {
  BottomSheet,
  Button,
  CarIcon,
  Chip,
  CountdownRing,
  DriverCard,
  FloatingIconButton,
  Input,
  ListRow,
  PaymentMethodPicker,
  RatingStars,
  showToast,
  Skeleton,
  StatusIcon,
  StatusPill,
  Stepper,
  Tag,
  TariffCard,
  TariffCarousel,
  ToastCard,
} from '@/components/ui-kit'
import { cn } from '@/lib/utils'

const TARIFFS = [
  { id: 'economy', name: 'Эконом', price: '2 200 ₸' },
  { id: 'comfort', name: 'Комфорт', price: '2 925 ₸' },
  { id: 'comfort_plus', name: 'Комфорт+', price: '3 600 ₸' },
  { id: 'business', name: 'Бизнес', price: '4 800 ₸' },
]

const PICKUP = { latitude: 43.2399, longitude: 76.915 }
const DROPOFF = { latitude: 43.2185, longitude: 76.9282 }
const DRIVER = { latitude: 43.2455, longitude: 76.9105 }

/** A kit section; `figma` is the node it mirrors, used by the visual comparison script. */
function Frame({
  title,
  figma,
  children,
  className,
}: {
  title: string
  figma: string
  children: ReactNode
  className?: string
}) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-label text-text-secondary uppercase">
        {title} <span className="font-normal text-text-tertiary">· Figma {figma}</span>
      </h2>
      <div data-figma={figma} className={cn('w-fit max-w-full overflow-x-auto rounded-lg bg-bg-canvas p-6', className)}>
        {children}
      </div>
    </section>
  )
}

function useTicker(total: number) {
  const [seconds, setSeconds] = useState(total)
  useEffect(() => {
    const timer = window.setInterval(() => setSeconds((value) => (value <= 0 ? total : value - 1)), 1000)
    return () => window.clearInterval(timer)
  }, [total])
  return seconds
}

function Buttons() {
  return (
    <Frame title="Button" figma="2:126" className="bg-bg-subtle">
      <div className="grid grid-cols-[repeat(3,120px)] items-start gap-4">
        <Button className="w-[120px]">Заказать</Button>
        <Button size="md" className="w-[120px]">Заказать</Button>
        <Button variant="secondary" className="w-[120px]">Заказать</Button>
        <Button variant="secondary" size="md" className="w-[120px]">Заказать</Button>
        <Button variant="ghost" className="w-[120px]">Заказать</Button>
        <Button variant="ghost" size="md" className="w-[120px]">Заказать</Button>
        <Button variant="danger" className="w-[120px]">Заказать</Button>
        <Button variant="danger" size="md" className="w-[120px]">Заказать</Button>
        <Button loading className="w-[120px]">Заказать</Button>
      </div>
    </Frame>
  )
}

function Pills() {
  return (
    <Frame title="StatusPill" figma="2:139">
      <div className="flex flex-wrap gap-3">
        {(['neutral', 'success', 'warning', 'danger', 'info', 'inverse'] as const).map((tone) => (
          <StatusPill key={tone} tone={tone}>
            Ищем водителя
          </StatusPill>
        ))}
      </div>
    </Frame>
  )
}

function ChipsAndTags() {
  const [filter, setFilter] = useState('all')
  const [tags, setTags] = useState<Record<string, boolean>>({ Вежливый: true })
  return (
    <>
      <Frame title="Chip" figma="2:144">
        <div className="flex flex-wrap gap-3">
          {[
            ['all', 'Все'],
            ['done', 'Завершённые'],
            ['cancelled', 'Отменённые'],
          ].map(([id, label]) => (
            <Chip key={id} selected={filter === id} onClick={() => setFilter(id as string)}>
              {label}
            </Chip>
          ))}
        </div>
      </Frame>
      <Frame title="Tag" figma="30:126">
        <div className="flex flex-wrap gap-1.5">
          {['Вежливый', 'Чисто', 'Аккуратно'].map((label) => (
            <Tag
              key={label}
              selected={Boolean(tags[label])}
              onSelectedChange={(selected) => setTags((current) => ({ ...current, [label]: selected }))}
            >
              {label}
            </Tag>
          ))}
        </div>
      </Frame>
    </>
  )
}

function Ratings() {
  const [value, setValue] = useState(4)
  return (
    <Frame title="RatingStars" figma="30:119">
      <div className="flex flex-col gap-3">
        {[0, 1, 2, 3, 4, 5].map((stars) => (
          <RatingStars key={stars} value={stars} readOnly label={`Пример ${stars}`} />
        ))}
        <p className="pt-2 text-caption text-text-secondary">Интерактивно (клик, ←/→, Home/End): {value}</p>
        <RatingStars value={value} onChange={setValue} />
      </div>
    </Frame>
  )
}

function Inputs() {
  const [query, setQuery] = useState('')
  return (
    <Frame title="Input" figma="3:96" className="w-[390px] px-4">
      <div className="flex w-[358px] max-w-full flex-col gap-3">
        <Input icon={Search} placeholder="Куда едем?" value={query} onChange={(event) => setQuery(event.target.value)} />
        <Input icon={Search} placeholder="Куда едем?" defaultValue="Куда едем?" focused readOnly />
      </div>
    </Frame>
  )
}

function Rows() {
  return (
    <Frame title="ListRow" figma="3:97" className="w-[390px] px-4">
      <div className="w-[358px] max-w-full">
        <ListRow icon={MapPin} title="Mega Alma-Ata" subtitle="пр. Розыбакиева, 247А" trailing="1 840 ₸" />
        <ListRow icon={Clock} title="Esentai Mall" subtitle="пр. Аль-Фараби, 77/8" onClick={() => undefined} />
      </div>
    </Frame>
  )
}

function Navs() {
  return (
    <Frame title="BottomNav" figma="3:85" className="w-[422px] bg-bg-subtle px-0 py-2">
      <div className="flex w-[390px] flex-col gap-4">
        <BottomNav role="passenger" pathname="/" preview />
        <BottomNav role="driver" pathname="/driver" preview />
        <BottomNav role="admin" pathname="/admin" preview />
      </div>
    </Frame>
  )
}

function Cars() {
  return (
    <Frame title="CarIcon" figma="20:53">
      <div className="flex gap-6">
        {(['economy', 'comfort', 'comfort_plus', 'business'] as const).map((carClass) => (
          <CarIcon key={carClass} carClass={carClass} />
        ))}
      </div>
    </Frame>
  )
}

function Tariffs() {
  const [tariff, setTariff] = useState('economy')
  return (
    <>
      <Frame title="TariffCard" figma="21:81">
        <div role="radiogroup" aria-label="Пример тарифов" className="flex gap-3">
          <TariffCard name="Эконом" price="2 200 ₸" selected />
          <TariffCard name="Эконом" price="2 200 ₸" />
        </div>
      </Frame>
      <Frame title="TariffCarousel" figma="21:682" className="w-[390px] max-w-full px-4">
        <TariffCarousel options={TARIFFS} value={tariff} onChange={setTariff} />
      </Frame>
    </>
  )
}

function Payments() {
  const [method, setMethod] = useState<PaymentMethod>('kaspi_link')
  return (
    <Frame title="PaymentMethodCard" figma="12:545" className="w-[390px] max-w-full px-4">
      <div className="w-[358px] max-w-full">
        <PaymentMethodPicker value={method} onChange={setMethod} />
      </div>
    </Frame>
  )
}

function DriverBits() {
  const seconds = useTicker(30)
  const [step, setStep] = useState(0)
  return (
    <>
      <Frame title="DriverCard" figma="5:451" className="w-[390px] max-w-full px-4">
        <div className="w-[358px] max-w-full">
          <DriverCard name="Арман Н." vehicle="Toyota Camry · серо-синий" plate="123 ABC 02" />
        </div>
      </Frame>
      <Frame title="Stepper" figma="6:330" className="w-[390px] max-w-full px-4">
        <div className="flex w-[358px] max-w-full flex-col gap-4">
          <Stepper steps={['Назначен', 'На месте', 'В пути', 'Готово']} current={step} />
          <Button variant="secondary" size="md" onClick={() => setStep((value) => (value + 1) % 4)}>
            Следующий шаг
          </Button>
        </div>
      </Frame>
      <Frame title="CountdownRing" figma="6:203">
        <div className="flex items-center gap-6">
          <CountdownRing seconds={24} />
          <CountdownRing seconds={seconds} />
        </div>
      </Frame>
    </>
  )
}

function Feedback() {
  return (
    <>
      <Frame title="StatusIcon" figma="23:258">
        <div className="flex items-center gap-4">
          <StatusIcon icon={Check} tone="success" />
          <StatusIcon icon={X} size={64} />
          <StatusIcon icon={Banknote} />
          <StatusIcon icon={Navigation} size={64} />
          <StatusIcon icon={Receipt} size={80} />
        </div>
      </Frame>
      <Frame title="FloatingIconButton" figma="4:158" className="bg-map-land">
        <div className="flex gap-4">
          <FloatingIconButton icon={Menu} aria-label="Меню" />
          <FloatingIconButton icon={Locate} aria-label="Моё местоположение" />
          <FloatingIconButton icon={ArrowLeft} aria-label="Назад" />
        </div>
      </Frame>
      <Frame title="Toast" figma="23:350" className="w-[390px] max-w-full px-4">
        <div className="flex w-[358px] max-w-full flex-col gap-4">
          <ToastCard
            icon={Car}
            title="Водитель отказался от заказа"
            description="Уже ищем другого — оплата сохранится за новым водителем"
          />
          <Button
            variant="secondary"
            size="md"
            onClick={() =>
              showToast({
                icon: Car,
                title: 'Водитель отказался от заказа',
                description: 'Уже ищем другого — оплата сохранится за новым водителем',
              })
            }
          >
            Показать toast
          </Button>
        </div>
      </Frame>
      <Frame title="Skeleton" figma="—" className="w-[390px] max-w-full px-4">
        <div className="flex w-[358px] max-w-full flex-col gap-3">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-16 w-full rounded-lg" />
        </div>
      </Frame>
    </>
  )
}

function SheetDemo() {
  const [tariff, setTariff] = useState('economy')
  const [method, setMethod] = useState<PaymentMethod>('cash')
  const [key, setKey] = useState(0)
  const [sheetHeight, setSheetHeight] = useState(0)
  const insets = useMapInsets(sheetHeight)
  return (
    <Frame title="MapView + BottomSheet" figma="4:253 / 7:2" className="w-full p-0 lg:w-[1100px]">
      <div className="relative h-[700px] w-full overflow-hidden rounded-lg [--sheet-offset:0px]">
        <MapView pickup={PICKUP} dropoff={DROPOFF} driver={DRIVER} me={PICKUP} insets={insets} />
        <FloatingIconButton icon={ArrowLeft} aria-label="Назад" className="absolute top-4 left-4 z-10 lg:hidden" />
        <BottomSheet key={key} aria-label="Пример шторки" onHeightChange={setSheetHeight}>
          <div className="flex w-full flex-col gap-1">
            <p className="text-body-medium">ул. Абая, 52 → Esentai Mall</p>
            <p className="text-caption text-text-secondary">10 км · 25 мин</p>
          </div>
          <TariffCarousel options={TARIFFS} value={tariff} onChange={setTariff} />
          <PaymentMethodPicker value={method} onChange={setMethod} />
          <Button className="w-full" onClick={() => setKey((value) => value + 1)}>
            Заказать Эконом
          </Button>
        </BottomSheet>
      </div>
    </Frame>
  )
}

/** Dev-only showcase of the UI kit for side-by-side checks against Figma (route /dev/kit). */
export function KitPage() {
  return (
    <div className="min-h-dvh bg-bg-subtle pb-16">
      <div className="hidden lg:block" data-figma="7:62">
        <TopBar role="passenger" displayName="Айгерим" pathname="/" preview />
      </div>
      <div className="mx-auto flex max-w-[1240px] flex-col gap-8 px-4 py-8">
        <header className="flex flex-col gap-2">
          <h1 className="text-display">UI kit</h1>
          <p className="text-body text-text-secondary">
            Компоненты BIS Taxi по Figma 6VHeDBRKk6RWdTYqH0r66K. Только в режиме разработки.
          </p>
        </header>
        <div className="grid gap-8 lg:grid-cols-2">
          <div className="flex min-w-0 flex-col gap-8">
            <Buttons />
            <Pills />
            <ChipsAndTags />
            <Ratings />
            <Inputs />
            <Rows />
          </div>
          <div className="flex min-w-0 flex-col gap-8">
            <Navs />
            <Cars />
            <Tariffs />
            <Payments />
            <DriverBits />
            <Feedback />
          </div>
        </div>
        <SheetDemo />
      </div>
    </div>
  )
}

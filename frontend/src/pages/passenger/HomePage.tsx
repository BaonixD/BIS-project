import { useState } from 'react'
import { useHideBottomNav } from '@/components/layout/nav-visibility'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { ArrowLeft, Menu } from 'lucide-react'
import { ACTIVE_RIDE_STATUSES, isApiError, type Coordinates, type PaymentMethod } from '@/api'
import type { Tariff } from '@/api/passenger-types'
import { FitToPoints, type MapInsets } from '@/components/map/layers'
import { MapView } from '@/components/map/MapView'
import { useMapInsets } from '@/components/map/use-map-insets'
import { MapLayout, MapOverlay, RoundButton } from '@/components/passenger/layout'
import { CenterPin, PIN_MAP_CLASS, PinTracker } from '@/components/passenger/map-layers'
import { usePlaceTitle } from '@/components/passenger/ride-text'
import { FloatingIconButton } from '@/components/ui-kit'
import { useReverseGeocode } from '@/hooks/use-geocoding'
import { newIdempotencyKey, useActiveRide, useCreateRide, useRouteQuote } from '@/hooks/use-rides'
import { useDebouncedValue } from '@/lib/geocoding'
import { AddressSearchScreen } from './home/AddressSearchScreen'
import { ChooseRideSheet } from './home/ChooseRideSheet'
import { isReorderState, type ReorderState, type Step, type Target } from './home/flow'
import { HomeSheet } from './home/HomeSheet'
import { MapPointSheet } from './home/MapPointSheet'
import { RouteErrorSheet } from './home/RouteErrorSheet'
import { useMyLocation } from './home/use-my-location'
import { passengerErrorMessage, routeErrorText } from './model/errors'
import { openKaspiLink } from './model/order'
import { readRecentPlaces, rememberPlace, suggestedPlaces } from './model/places'

interface ChosenPoint {
  point: Coordinates
  title?: string
  subtitle?: string
}

/** Bottom nav pill overlapping the home sheet (AppShell `--sheet-offset`). */
const HOME_SHEET_OFFSET = 72

/** Figma Home 4:94: «me» sits 55px above the sheet, not in the middle of the free map. */
function homeInsets(insets: MapInsets, sheetHeight: number): MapInsets {
  if (insets.left || sheetHeight === 0) return insets
  const sheetTop = window.innerHeight - HOME_SHEET_OFFSET - sheetHeight
  return { top: Math.max(0, sheetTop - 123), bottom: Math.max(0, window.innerHeight - sheetTop - 13) }
}

const QUOTE_RETRY_CODES = ['quote_expired', 'quote_already_used', 'quote_not_found']

function initialStep(reorder: ReorderState | null): Step {
  if (!reorder) return { name: 'home' }
  return reorder.step === 'choose' ? { name: 'choose' } : { name: 'search', target: 'dropoff' }
}

function AddressChip({ label, title }: { label: string; title: string | undefined }) {
  return (
    <div className="flex items-center gap-2 rounded-full bg-bg-canvas px-3.5 py-2.5 whitespace-nowrap shadow-card">
      <span className="text-caption text-text-secondary">{label}</span>
      <span className="max-w-[200px] truncate text-callout text-text-primary">{title ?? '…'}</span>
    </div>
  )
}

/** Passenger home: where to → address search or a map point → tariffs and payment → order. */
export function HomePage() {
  const navigate = useNavigate()
  const { state } = useLocation()
  const reorder = isReorderState(state) ? state : null
  const activeRide = useActiveRide(ACTIVE_RIDE_STATUSES)
  const me = useMyLocation()

  const [step, setStep] = useState<Step>(() => initialStep(reorder))
  useHideBottomNav(step.name !== 'home')
  const [pickup, setPickup] = useState<ChosenPoint | null>(reorder ? { point: reorder.pickup } : null)
  const [dropoff, setDropoff] = useState<ChosenPoint | null>(reorder ? { point: reorder.dropoff } : null)
  const [tariff, setTariff] = useState<Tariff>(reorder?.tariff ?? 'economy')
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>(reorder?.paymentMethod ?? 'cash')
  const [pinPoint, setPinPoint] = useState<Coordinates | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)
  const [sheetHeight, setSheetHeight] = useState(0)
  const insets = useMapInsets(sheetHeight)

  const pickupPoint = pickup?.point ?? me.point
  const pickupAddress = usePlaceTitle(pickupPoint)
  const dropoffAddress = usePlaceTitle(dropoff?.point)
  const pickupTitle = pickup?.title ?? pickupAddress ?? 'Моё местоположение'
  const dropoffTitle = dropoff?.title ?? dropoffAddress ?? 'Точка на карте'

  const choosing = step.name === 'choose' && dropoff !== null
  const quote = useRouteQuote(choosing ? { pickup: pickupPoint, dropoff: dropoff.point } : null)
  const createRide = useCreateRide()
  const pinPlace = useReverseGeocode(useDebouncedValue(step.name === 'map' ? pinPoint : null, 400)).data

  // Not while refetching: the cached ride may have finished since (back home after the receipt).
  if (activeRide.data && !activeRide.isFetching) return <Navigate to={`/ride/${activeRide.data.id}`} replace />

  const choose = (target: Target, place: ChosenPoint) => {
    setLocalError(null)
    createRide.reset()
    if (target === 'pickup') setPickup(place)
    else setDropoff(place)
    const hasDropoff = target === 'dropoff' || dropoff !== null
    setStep(hasDropoff ? { name: 'choose' } : { name: 'search', target: 'dropoff' })
  }

  const openMap = (target: Target, start?: Coordinates) => {
    setPinPoint(null)
    const current = target === 'pickup' ? pickupPoint : dropoff?.point
    setStep({ name: 'map', target, start: start ?? current ?? pickupPoint })
  }

  const order = () => {
    if (!quote.data || !dropoff) return
    setLocalError(null)
    if (openKaspiLink(paymentMethod, quote.data.kaspi_payment_url) === 'unavailable') {
      setLocalError(passengerErrorMessage({ code: 'kaspi_unavailable' }))
      return
    }
    createRide.mutate(
      { quoteId: quote.data.quote_id, paymentMethod, tariff, idempotencyKey: newIdempotencyKey() },
      {
        onSuccess: (ride) => {
          if (dropoff.title) rememberPlace({ id: ride.id, title: dropoff.title, subtitle: dropoff.subtitle ?? '', point: dropoff.point })
          navigate(`/ride/${ride.id}`, { replace: true })
        },
        onError: (error) => {
          if (isApiError(error, 'active_ride_exists')) void activeRide.refetch()
          if (QUOTE_RETRY_CODES.some((code) => isApiError(error, code))) void quote.refetch()
        },
      },
    )
  }

  const orderError = localError ?? (createRide.error ? passengerErrorMessage(createRide.error) : null)
  const routeFailed = choosing && quote.isError

  const map = (
    <MapView
      center={pickupPoint}
      me={step.name === 'home' ? me.point : null}
      pickup={choosing && !quote.isError ? pickupPoint : null}
      dropoff={choosing && !quote.isError ? dropoff.point : null}
      route={choosing ? quote.data?.route : null}
      insets={insets}
      fit={choosing && sheetHeight > 0}
      onPick={step.name === 'home' ? (point) => openMap('dropoff', point) : undefined}
    >
      {step.name === 'home' && <FitToPoints points={[me.point]} insets={homeInsets(insets, sheetHeight)} />}
      {step.name === 'map' && (
        <PinTracker key={`${step.start.latitude},${step.start.longitude}`} start={step.start} onChange={setPinPoint} />
      )}
    </MapView>
  )

  if (step.name === 'map') {
    const done = () => {
      if (!pinPoint || !pinPlace) return
      choose(step.target, { point: pinPoint, title: pinPlace.title, subtitle: pinPlace.subtitle })
    }
    return (
      <MapLayout
        map={map}
        mapClassName={PIN_MAP_CLASS}
        onSheetHeightChange={setSheetHeight}
        sheetClassName="pb-7"
        overlay={
          <>
            <MapOverlay>
              <RoundButton elevated label="Назад" onClick={() => setStep({ name: 'search', target: step.target })} />
              <AddressChip label={step.target === 'pickup' ? 'Откуда' : 'Куда'} title={pinPlace?.title} />
            </MapOverlay>
            <CenterPin />
          </>
        }
        sheet={<MapPointSheet target={step.target} place={pinPoint ? pinPlace : undefined} onDone={done} />}
      />
    )
  }

  if (step.name === 'choose' && dropoff) {
    return (
      <MapLayout
        map={map}
        onSheetHeightChange={setSheetHeight}
        centered={routeFailed}
        sheetClassName={routeFailed ? 'gap-[18px]' : 'gap-3 lg:gap-4'}
        overlay={
          !routeFailed && (
            <MapOverlay className="lg:hidden">
              <FloatingIconButton icon={ArrowLeft} aria-label="Назад" onClick={() => setStep({ name: 'home' })} />
            </MapOverlay>
          )
        }
        sheet={
          routeFailed ? (
            <RouteErrorSheet
              text={routeErrorText(quote.error)}
              retrying={quote.isFetching}
              onRetry={() => void quote.refetch()}
              onEdit={() => setStep({ name: 'search', target: 'dropoff' })}
            />
          ) : (
            <ChooseRideSheet
              pickupTitle={pickupTitle}
              dropoffTitle={dropoffTitle}
              quote={quote.data}
              tariff={tariff}
              onTariffChange={setTariff}
              paymentMethod={paymentMethod}
              onPaymentMethodChange={(method) => {
                setLocalError(null)
                setPaymentMethod(method)
              }}
              ordering={createRide.isPending}
              error={orderError}
              onOrder={order}
              onEdit={(target) => setStep({ name: 'search', target })}
            />
          )
        }
      />
    )
  }

  return (
    <>
      <MapLayout
        map={map}
        overNav={false}
        onSheetHeightChange={setSheetHeight}
        overlay={
          <MapOverlay>
            <FloatingIconButton icon={Menu} aria-label="Меню" onClick={() => navigate('/profile')} />
          </MapOverlay>
        }
        sheet={
          <HomeSheet
            places={suggestedPlaces(readRecentPlaces())}
            onSearch={() => setStep({ name: 'search', target: 'dropoff' })}
            onPickOnMap={() => openMap('dropoff')}
            onPlace={(place) => choose('dropoff', place)}
          />
        }
      />
      {step.name === 'search' && (
        <AddressSearchScreen
          target={step.target}
          pickupText={pickup?.title ?? `Моё местоположение${pickupAddress ? ` · ${pickupAddress}` : ''}`}
          dropoffText={dropoff ? dropoffTitle : null}
          origin={pickupPoint}
          onTargetChange={(target) => setStep({ name: 'search', target })}
          onSelect={(place) => choose(step.target, place)}
          onPickOnMap={() => openMap(step.target)}
          onBack={() => setStep(dropoff ? { name: 'choose' } : { name: 'home' })}
        />
      )}
    </>
  )
}


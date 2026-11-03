import type { DriverProfileUpdate } from '@/api'
import type { NextDriver } from '@/api/driver-types'

export interface SettingsForm {
  full_name: string
  phone: string
  license_number: string
  /** «Toyota Camry»: make and model in one field, as in Figma 26:500. */
  car: string
  color: string
  plate_number: string
  year: string
}

export function settingsForm(driver: NextDriver): SettingsForm {
  const vehicle = driver.vehicle
  return {
    full_name: driver.full_name ?? '',
    phone: driver.phone ?? '',
    license_number: driver.license_number ?? '',
    car: vehicle ? `${vehicle.make} ${vehicle.model}` : '',
    color: vehicle?.color ?? '',
    plate_number: vehicle?.plate_number ?? '',
    year: vehicle ? String(vehicle.year) : '',
  }
}

/** PATCH body: empty fields are left out; the vehicle goes only when make, model, colour, plate and year are set. */
export function settingsUpdate(form: SettingsForm): DriverProfileUpdate {
  const text = (value: string) => value.trim() || undefined
  const [make = '', ...modelWords] = form.car.trim().split(/\s+/)
  const model = modelWords.join(' ')
  const year = Number(form.year)
  const vehicleReady = make && model && form.color.trim() && form.plate_number.trim() && Number.isInteger(year) && year > 0
  return {
    full_name: text(form.full_name),
    phone: text(form.phone),
    license_number: text(form.license_number),
    vehicle: vehicleReady
      ? { make, model, color: form.color.trim(), plate_number: form.plate_number.trim(), year }
      : undefined,
  }
}

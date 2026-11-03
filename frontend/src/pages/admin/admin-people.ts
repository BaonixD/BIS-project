import { useMemo } from 'react'
import { useAdminDrivers, useAdminUsers } from '@/hooks/use-admin'
import { shortName } from './admin-format'

const LIMIT = 100

/** Names for ride rows: users by id (display name or username), drivers by their full name. */
export function useAdminNames() {
  const users = useAdminUsers(undefined, { limit: LIMIT })
  const drivers = useAdminDrivers(undefined, { limit: LIMIT })
  return useMemo(() => {
    const userNames = new Map((users.data?.items ?? []).map((user) => [user.id, user.display_name ?? user.username]))
    const driverNames = new Map(
      (drivers.data?.items ?? []).flatMap((driver) => (driver.full_name ? [[driver.id, shortName(driver.full_name)] as const] : [])),
    )
    return {
      passenger: (id: string) => userNames.get(id) ?? 'Пассажир',
      driver: (id: string | null) => (id ? (driverNames.get(id) ?? userNames.get(id) ?? 'Водитель') : null),
    }
  }, [users.data, drivers.data])
}

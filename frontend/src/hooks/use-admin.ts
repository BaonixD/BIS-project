import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type ApprovalStatus, type Page, type PageParams, type UserRole } from '@/api'
import {
  patchDriverCarClass,
  postApproveDriver,
  type NextAdminDriver,
  type Tariff,
} from '@/api/driver-types'
import { queryKeys, type AdminRideFilters } from './query-keys'

export function useAdminDrivers(approvalStatus: ApprovalStatus | undefined, page: PageParams = {}) {
  return useQuery({
    queryKey: queryKeys.admin.drivers(approvalStatus, page),
    queryFn: async () =>
      (await unwrap(
        api.GET('/api/v1/admin/drivers', {
          params: { query: { approval_status: approvalStatus, ...page } },
        }),
      )) as Page<NextAdminDriver>,
    placeholderData: keepPreviousData,
  })
}

export interface ApproveDriverVariables {
  driverId: string
  /** Optional: without it the backend keeps the current class (a new car is economy). */
  carClass: Tariff | null
}

function useInvalidateDrivers() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: ['admin', 'drivers'] })
}

export function useApproveDriver() {
  const invalidate = useInvalidateDrivers()
  return useMutation({
    mutationFn: ({ driverId, carClass }: ApproveDriverVariables) => postApproveDriver(driverId, carClass),
    onSettled: invalidate,
  })
}

export function useSetCarClass() {
  const invalidate = useInvalidateDrivers()
  return useMutation({
    mutationFn: ({ driverId, carClass }: { driverId: string; carClass: Tariff }) =>
      patchDriverCarClass(driverId, carClass),
    onSettled: invalidate,
  })
}

export function useAdminRides(filters: AdminRideFilters) {
  return useQuery({
    queryKey: queryKeys.admin.rides(filters),
    queryFn: () => unwrap(api.GET('/api/v1/admin/rides', { params: { query: filters } })),
    placeholderData: keepPreviousData,
  })
}

export function useAdminUsers(role: UserRole | undefined, page: PageParams = {}) {
  return useQuery({
    queryKey: queryKeys.admin.users(role, page),
    queryFn: () =>
      unwrap(api.GET('/api/v1/admin/users', { params: { query: { role, ...page } } })),
    placeholderData: keepPreviousData,
  })
}

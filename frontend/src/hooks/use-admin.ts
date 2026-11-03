import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type ApprovalStatus, type PageParams, type UserRole } from '@/api'
import { queryKeys, type AdminRideFilters } from './query-keys'

export function useAdminDrivers(approvalStatus: ApprovalStatus | undefined, page: PageParams = {}) {
  return useQuery({
    queryKey: queryKeys.admin.drivers(approvalStatus, page),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/admin/drivers', {
          params: { query: { approval_status: approvalStatus, ...page } },
        }),
      ),
    placeholderData: keepPreviousData,
  })
}

export function useApproveDriver() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (driverId: string) =>
      unwrap(
        api.POST('/api/v1/admin/drivers/{driver_id}/approve', {
          params: { path: { driver_id: driverId } },
        }),
      ),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['admin', 'drivers'] }),
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

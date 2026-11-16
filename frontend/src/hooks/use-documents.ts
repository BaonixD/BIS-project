import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { request, jsonBody } from '@/api/request'
import type { components } from '@/api/schema'

export type DocumentsSummary = components['schemas']['DocumentsSummary']
export type DriverDocument = components['schemas']['DocumentView']
export type DocumentKind = DriverDocument['kind']

export function useDocuments(driverId?: string, packageId?: string) {
  return useQuery({ queryKey: ['documents', driverId ?? 'me', packageId], queryFn: () => request<DocumentsSummary>(driverId ? `/admin/drivers/${driverId}/documents${packageId ? `?package_id=${packageId}` : ''}` : '/drivers/me/documents'), refetchInterval: driverId ? false : 20_000 })
}

export function useDocumentAction(driverId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (action: { type: 'upload'; kind: DocumentKind; file: File } | { type: 'delete'; kind: DocumentKind } | { type: 'submit' | 'revise'; package: NonNullable<DocumentsSummary['package']> } | { type: 'reject'; package: NonNullable<DocumentsSummary['package']>; reason: string } | { type: 'request'; reason: string }) => {
      if (action.type === 'upload') { const form = new FormData(); form.set('file', action.file); return request<DocumentsSummary>(`/drivers/me/documents/${action.kind}`, { method: 'PUT', body: form }) }
      if (action.type === 'delete') return request<DocumentsSummary>(`/drivers/me/documents/${action.kind}`, { method: 'DELETE' })
      if (action.type === 'request') return request<DocumentsSummary>(`/admin/drivers/${driverId}/documents/request`, { method: 'POST', ...jsonBody({ reason: action.reason }) })
      const body = { package_id: action.package.id, version: action.package.version, ...(action.type === 'reject' ? { reason: action.reason } : {}) }
      return request<DocumentsSummary>(action.type === 'reject' ? `/admin/drivers/${driverId}/documents/reject` : `/drivers/me/documents/${action.type}`, { method: 'POST', ...jsonBody(body) })
    },
    onSuccess: async () => { await Promise.all([client.invalidateQueries({ queryKey: ['documents'] }), client.invalidateQueries({ queryKey: ['admin'] }), client.invalidateQueries({ queryKey: ['drivers'] })]) },
  })
}

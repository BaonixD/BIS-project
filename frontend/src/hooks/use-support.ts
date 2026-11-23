import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { request, jsonBody } from '@/api/request'
import type { components } from '@/api/schema'

export type Ticket = components['schemas']['TicketView']
export type SupportMessage = components['schemas']['MessageView']
export type MessagePage = components['schemas']['MessagePage']
export type TicketPage = components['schemas']['Page_TicketView_']
export type Category = components['schemas']['CreateTicket']['category']

export function useSupportTickets(
  admin: boolean,
  filters: { status?: string; category?: string; q?: string; offset?: number },
) {
  const query = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value))
  })
  query.set('limit', '20')
  return useQuery({
    queryKey: ['support', 'tickets', admin, filters],
    queryFn: () => request<TicketPage>(`${admin ? '/admin' : ''}/support/tickets?${query}`),
    refetchInterval: 20_000,
  })
}

export function useSupportUnread() {
  return useQuery({
    queryKey: ['support', 'unread'],
    queryFn: () => request<{ count: number }>('/support/unread'),
    refetchInterval: 20_000,
    retry: false,
  })
}

export function useSupportTicket(id: string) {
  return useQuery({
    queryKey: ['support', 'ticket', id],
    queryFn: () => request<Ticket>(`/support/tickets/${id}`),
    enabled: Boolean(id),
    refetchInterval: 5_000,
  })
}

export function useSupportAction() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (
      action:
        | { type: 'create'; body: components['schemas']['CreateTicket'] }
        | { type: 'send'; id: string; body: components['schemas']['SendMessage'] }
        | { type: 'status'; id: string; status: 'in_progress' | 'resolved' }
        | { type: 'handoff'; id: string },
    ): Promise<Ticket | SupportMessage> => {
      if (action.type === 'create')
        return request<Ticket>('/support/tickets', { method: 'POST', ...jsonBody(action.body) })
      if (action.type === 'handoff')
        return request<Ticket>(`/support/tickets/${action.id}/handoff`, { method: 'POST' })
      if (action.type === 'send')
        return request<SupportMessage>(`/support/tickets/${action.id}/messages`, {
          method: 'POST',
          ...jsonBody(action.body),
        })
      return request<Ticket>(`/admin/support/tickets/${action.id}`, {
        method: 'PATCH',
        ...jsonBody({ status: action.status }),
      })
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ['support'] }),
  })
}

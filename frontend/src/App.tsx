import { useState } from 'react'
import { AppStatus } from '@/components/common/AppStatus'
import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router/dom'
import { SessionProvider } from '@/auth/SessionProvider'
import { Toaster } from '@/components/ui-kit'
import { createQueryClient } from '@/lib/query-client'
import { router } from '@/routes/router'

export default function App() {
  const [queryClient] = useState(createQueryClient)
  return (
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <RouterProvider router={router} />
        <Toaster />
        <AppStatus />
      </SessionProvider>
    </QueryClientProvider>
  )
}

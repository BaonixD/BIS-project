import { StrictMode } from 'react'
import '@/lib/theme'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { setupPwa } from '@/lib/pwa'

setupPwa()

const root = document.getElementById('root')
if (!root) throw new Error('Missing #root element')

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

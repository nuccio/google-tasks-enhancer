// Entry point of the local read-only data viewer (#43). It imports nothing from the main app.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './dev.css'
import DevApp from './DevApp.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DevApp />
  </StrictMode>,
)

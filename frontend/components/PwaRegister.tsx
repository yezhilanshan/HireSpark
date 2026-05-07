'use client'

import { useEffect } from 'react'

export function PwaRegister() {
  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return

    navigator.serviceWorker.register('/sw.js', { scope: '/' }).then(
      (registration) => {
        console.log('[PWA] Service Worker registered:', registration.scope)
      },
      (error) => {
        console.warn('[PWA] Service Worker registration failed:', error)
      }
    )

    // Listen for new SW updates
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      window.location.reload()
    })
  }, [])

  return null
}

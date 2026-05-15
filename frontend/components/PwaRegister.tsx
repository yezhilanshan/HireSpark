'use client'

import { useEffect } from 'react'

export function PwaRegister() {
  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return

    if (process.env.NODE_ENV !== 'production') {
      navigator.serviceWorker.getRegistrations?.().then((registrations) => {
        registrations.forEach((registration) => {
          registration.unregister().catch(() => undefined)
        })
      })
      if ('caches' in window) {
        window.caches.keys().then((keys) => {
          keys.forEach((key) => {
            window.caches.delete(key).catch(() => undefined)
          })
        })
      }
      return
    }

    navigator.serviceWorker.register('/sw.js', { scope: '/' }).then(
      (registration) => {
        console.log('[PWA] Service Worker registered:', registration.scope)
      },
      (error) => {
        console.warn('[PWA] Service Worker registration failed:', error)
      }
    )

    // Listen for new SW updates
    let refreshing = false
    const handleControllerChange = () => {
      if (refreshing) return
      refreshing = true
      window.location.reload()
    }
    navigator.serviceWorker.addEventListener('controllerchange', handleControllerChange)

    return () => {
      navigator.serviceWorker.removeEventListener('controllerchange', handleControllerChange)
    }
  }, [])

  return null
}

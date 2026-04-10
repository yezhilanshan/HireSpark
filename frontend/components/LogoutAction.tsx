'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import type { ReactNode } from 'react'

type LogoutActionProps = {
    className?: string
    children: ReactNode
}

export default function LogoutAction({ className = '', children }: LogoutActionProps) {
    const router = useRouter()
    const [submitting, setSubmitting] = useState(false)

    const handleLogout = async () => {
        if (submitting) return
        setSubmitting(true)
        try {
            await fetch('/api/auth/logout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            })
        } finally {
            router.replace('/')
            router.refresh()
            setSubmitting(false)
        }
    }

    return (
        <button type="button" className={className} onClick={handleLogout} disabled={submitting}>
            {children}
        </button>
    )
}

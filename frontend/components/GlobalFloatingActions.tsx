'use client'

import { usePathname } from 'next/navigation'
import AssistantFloatingChat from './AssistantFloatingChat'
import MembershipSubscriptionButton from './MembershipSubscriptionButton'
import NotificationCenter from './NotificationCenter'

export default function GlobalFloatingActions() {
    const pathname = usePathname()

    const isInterviewScene = pathname?.startsWith('/interview') || pathname?.startsWith('/liveness')
    const hideTopActions = pathname === '/'

    if (isInterviewScene) {
        return null
    }

    return (
        <>
            {!hideTopActions ? (
                <div className="fixed right-4 top-4 z-50 flex items-center gap-3">
                    <MembershipSubscriptionButton mode="inline" />
                    <NotificationCenter mode="inline" />
                </div>
            ) : null}
            <AssistantFloatingChat />
        </>
    )
}

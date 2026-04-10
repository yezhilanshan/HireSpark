'use client'

import { usePathname } from 'next/navigation'
import ThemeToggle from './ThemeToggle'
import AssistantFloatingChat from './AssistantFloatingChat'

export default function GlobalFloatingActions() {
    const pathname = usePathname()

    const isInterviewScene = pathname?.startsWith('/interview') || pathname?.startsWith('/liveness')
    // 登录页只隐藏顶部按钮，保留助理入口。
    const hideTopActions = pathname === '/'

    if (isInterviewScene) {
        return null
    }

    return (
        <>
            <AssistantFloatingChat />
            {!hideTopActions ? <ThemeToggle /> : null}
        </>
    )
}

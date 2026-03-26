'use client'

import { usePathname } from 'next/navigation'
import MyEntry from './MyEntry'
import ThemeToggle from './ThemeToggle'

export default function GlobalFloatingActions() {
    const pathname = usePathname()

    // 这些页面有自己的顶部操作区，避免右上角浮层遮挡。
    const shouldHide = pathname?.startsWith('/interview') || pathname?.startsWith('/liveness')

    if (shouldHide) {
        return null
    }

    return (
        <>
            <MyEntry />
            <ThemeToggle />
        </>
    )
}

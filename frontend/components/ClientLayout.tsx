'use client'

import dynamic from 'next/dynamic'

const CommandPalette = dynamic(() => import('@/components/command-palette').then((mod) => ({ default: mod.CommandPalette })), {
    ssr: false,
})
const GlobalFloatingActions = dynamic(() => import('@/components/GlobalFloatingActions'), {
    ssr: false,
})

export default function ClientLayout() {
    return (
        <>
            <GlobalFloatingActions />
            <CommandPalette />
        </>
    )
}

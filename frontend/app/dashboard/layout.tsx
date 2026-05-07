'use client'

import type { ReactNode } from 'react'
import PersistentSidebar from '@/components/PersistentSidebar'

export default function DashboardLayout({ children }: { children: ReactNode }) {
    return (
        <div className="flex min-h-screen bg-[#FAF9F6]">
            <PersistentSidebar />

            <main className="flex h-screen flex-1 flex-col overflow-hidden">{children}</main>
        </div>
    )
}

/**
 * 仪表板布局组件
 * 用于面试复盘页和报告页的统一布局结构
 */

import React, { ReactNode } from 'react'
import PersistentSidebar from '@/components/PersistentSidebar'

interface DashboardLayoutProps {
    children: ReactNode
    loading?: boolean
    error?: ReactNode
}

/**
 * 统一的仪表板布局 - Sidebar + Main 结构
 * P1-3 优化: 减少页面重复代码
 */
export function DashboardLayout({
    children,
    loading = false,
    error,
}: DashboardLayoutProps) {
    if (loading) {
        return (
            <div className="flex min-h-screen">
                <PersistentSidebar />
                <main className="flex-1 overflow-y-auto">
                    <div className="flex min-h-full items-center justify-center">
                        <div className="rounded-2xl border border-[#E5E5E5] bg-white px-8 py-10 text-center shadow-sm">
                            <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-[#111111] border-t-transparent" />
                            <p className="text-sm font-medium text-[#666666]">加载中...</p>
                        </div>
                    </div>
                </main>
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex min-h-screen">
                <PersistentSidebar />
                <main className="flex-1 overflow-y-auto">
                    <div className="mx-auto max-w-2xl px-6 py-8">
                        <section className="rounded-2xl border border-red-200 bg-red-50 p-8">
                            <p className="text-lg font-semibold text-red-700">加载失败</p>
                            <div className="mt-2 text-sm text-red-700/90">{error}</div>
                        </section>
                    </div>
                </main>
            </div>
        )
    }

    return (
        <div className="flex min-h-screen">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">{children}</main>
        </div>
    )
}

export default DashboardLayout

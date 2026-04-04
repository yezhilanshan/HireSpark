'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
    BookOpen,
    ClipboardList,
    Film,
    LayoutDashboard,
    LogOut,
    Settings,
} from 'lucide-react'

const MAIN_NAV_ITEMS = [
    { href: '/dashboard', label: '工作区', icon: LayoutDashboard },
    { href: '/dashboard/questions', label: '题库', icon: BookOpen },
    { href: '/history', label: '历史记录', icon: ClipboardList },
    { href: '/replay', label: '面试复盘', icon: Film },
]

const BOTTOM_NAV_ITEMS = [
    { href: '/settings', label: '系统设置', icon: Settings },
    { href: '/', label: '退出', icon: LogOut },
]

function isActive(pathname: string, href: string): boolean {
    if (href === '/') {
        return pathname === '/'
    }
    return pathname === href || pathname.startsWith(`${href}/`)
}

export default function PersistentSidebar() {
    const pathname = usePathname() || ''

    const shouldHideSidebar = pathname.startsWith('/interview') || pathname.startsWith('/interview-setup') || pathname.startsWith('/liveness')
    if (shouldHideSidebar) {
        return null
    }

    return (
        <aside className="hidden md:sticky md:top-0 md:block md:h-screen md:w-64 md:shrink-0 md:border-r md:border-[#E5E5E5] md:bg-[#FAF9F6]">
            <div className="flex h-full flex-col">
                <div className="h-16 border-b border-[#E5E5E5] px-6 flex items-center">
                    <Link href="/" className="text-lg font-serif italic font-medium text-[#111111]">
                        HireSpark
                    </Link>
                </div>

                <nav className="flex-1 space-y-1 px-4 py-6">
                    {MAIN_NAV_ITEMS.map((item) => {
                        const Icon = item.icon
                        const active = isActive(pathname, item.href)
                        return (
                            <Link
                                key={`${item.href}-${item.label}`}
                                href={item.href}
                                aria-current={active ? 'page' : undefined}
                                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                                    active
                                        ? 'bg-[#EBE9E0] text-[#111111]'
                                        : 'text-[#666666] hover:bg-[#F1F0EC] hover:text-[#111111]'
                                }`}
                            >
                                <Icon className="h-4 w-4 shrink-0" />
                                <span>{item.label}</span>
                            </Link>
                        )
                    })}
                </nav>

                <div className="space-y-1 border-t border-[#E5E5E5] p-4">
                    {BOTTOM_NAV_ITEMS.map((item) => {
                        const Icon = item.icon
                        const active = isActive(pathname, item.href)

                        return (
                            <Link
                                key={`${item.href}-${item.label}`}
                                href={item.href}
                                aria-current={active ? 'page' : undefined}
                                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                                    active
                                        ? 'bg-[#EBE9E0] text-[#111111]'
                                        : 'text-[#666666] hover:bg-[#F1F0EC] hover:text-[#111111]'
                                }`}
                            >
                                <Icon className="h-4 w-4 shrink-0" />
                                <span>{item.label}</span>
                            </Link>
                        )
                    })}
                </div>
            </div>
        </aside>
    )
}

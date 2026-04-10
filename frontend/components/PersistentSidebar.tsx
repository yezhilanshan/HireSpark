'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
    BarChart3,
    BookOpen,
    ClipboardList,
    Film,
    LayoutDashboard,
    LogOut,
    Settings,
} from 'lucide-react'
import LogoutAction from '@/components/LogoutAction'

const MAIN_NAV_ITEMS = [
    { href: '/dashboard', label: '工作台', icon: LayoutDashboard },
    { href: '/dashboard/questions', label: '题库中心', icon: BookOpen },
    { href: '/history', label: '历史记录', icon: ClipboardList },
    { href: '/replay', label: '面试复盘', icon: Film },
    { href: '/insights', label: '近期总结', icon: BarChart3 },
]

const BOTTOM_NAV_ITEMS = [{ href: '/settings', label: '设置', icon: Settings }]

function isActive(pathname: string, href: string): boolean {
    return pathname === href || pathname.startsWith(`${href}/`)
}

export default function PersistentSidebar() {
    const pathname = usePathname() || ''
    const shouldHideSidebar =
        pathname.startsWith('/interview') ||
        pathname.startsWith('/interview-setup') ||
        pathname.startsWith('/liveness')

    if (shouldHideSidebar) {
        return null
    }

    return (
        <aside className="hidden h-screen w-64 shrink-0 border-r border-[#E5E5E5] bg-[#FAF9F6] md:sticky md:top-0 md:block">
            <div className="flex h-full flex-col">
                <div className="flex h-16 items-center border-b border-[#E5E5E5] px-6">
                    <Link href="/dashboard" className="text-lg font-serif italic font-medium text-[#111111]">
                        PanelMind
                    </Link>
                </div>

                <nav className="flex-1 space-y-1 px-4 py-6">
                    {MAIN_NAV_ITEMS.map((item) => {
                        const Icon = item.icon
                        const active = isActive(pathname, item.href)
                        return (
                            <Link
                                key={item.href}
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
                                key={item.href}
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

                    <LogoutAction className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-[#666666] transition-colors hover:bg-[#F1F0EC] hover:text-[#111111]">
                        <LogOut className="h-4 w-4 shrink-0" />
                        <span>退出登录</span>
                    </LogoutAction>
                </div>
            </div>
        </aside>
    )
}

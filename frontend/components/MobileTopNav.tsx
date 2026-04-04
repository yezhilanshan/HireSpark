'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const NAV_ITEMS = [
    { href: '/dashboard', label: '工作区' },
    { href: '/dashboard/questions', label: '题库' },
    { href: '/history', label: '历史记录' },
    { href: '/replay', label: '面试复盘' },
    { href: '/settings', label: '系统设置' },
]

function isActive(pathname: string, href: string): boolean {
    if (href === '/') {
        return pathname === '/'
    }
    return pathname === href || pathname.startsWith(`${href}/`)
}

export default function MobileTopNav() {
    const pathname = usePathname() || ''

    const shouldHide = pathname.startsWith('/interview') || pathname.startsWith('/interview-setup') || pathname.startsWith('/liveness')
    if (shouldHide) {
        return null
    }

    return (
        <div className="border-b border-[#E5E5E5] bg-white/80 px-3 py-3 backdrop-blur md:hidden">
            <nav className="flex items-center gap-2 overflow-x-auto">
                {NAV_ITEMS.map((item) => {
                    const active = isActive(pathname, item.href)
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            aria-current={active ? 'page' : undefined}
                            className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                                active
                                    ? 'bg-[#EBE9E0] text-[#111111]'
                                    : 'text-[#666666] hover:bg-[#F5F5F5] hover:text-[#111111]'
                            }`}
                        >
                            {item.label}
                        </Link>
                    )
                })}
            </nav>
        </div>
    )
}

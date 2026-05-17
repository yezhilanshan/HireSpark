'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { BarChart3, History, LayoutDashboard, PlayCircle, UserCircle2 } from 'lucide-react'
import NotificationCenter from './NotificationCenter'

const NAV_ITEMS = [
    { href: '/', label: '概览', icon: LayoutDashboard },
    { href: '/interview-setup', label: '开始面试', icon: PlayCircle },
    { href: '/review', label: '单场复盘', icon: BarChart3 },
    { href: '/history', label: '历史记录', icon: History },
    { href: '/me', label: '个人中心', icon: UserCircle2 },
]

function isActive(pathname: string, href: string): boolean {
    if (href === '/') {
        return pathname === '/'
    }
    return pathname === href || pathname.startsWith(`${href}/`)
}

export default function CandidateTopNav() {
    const pathname = usePathname()

    if (pathname?.startsWith('/interview') || pathname?.startsWith('/liveness')) {
        return null
    }

    return (
        <header className="sticky top-0 z-40 border-b border-white/50 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/70">
            <div className="mx-auto flex w-full max-w-7xl items-center gap-4 px-4 py-3 sm:px-6">
                <Link href="/" className="shrink-0">
                    <div className="inline-flex items-center gap-2 rounded-full border border-cyan-700/20 bg-cyan-50/80 px-3 py-1.5 text-xs font-bold tracking-wide text-cyan-800 dark:border-cyan-300/30 dark:bg-cyan-900/20 dark:text-cyan-200">
                        职跃星辰
                    </div>
                </Link>

                <nav className="flex flex-1 items-center gap-2 overflow-x-auto whitespace-nowrap">
                    {NAV_ITEMS.map((item) => {
                        const Icon = item.icon
                        const active = isActive(pathname || '', item.href)

                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                aria-current={active ? 'page' : undefined}
                                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold transition ${
                                    active
                                        ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                                        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100'
                                }`}
                            >
                                <Icon className="h-4 w-4" />
                                {item.label}
                            </Link>
                        )
                    })}
                </nav>

                <div className="shrink-0">
                    <NotificationCenter mode="inline" />
                </div>
            </div>
        </header>
    )
}

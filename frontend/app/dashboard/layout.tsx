'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { motion } from 'motion/react'
import {
    BarChart3,
    BookOpen,
    Film,
    History,
    LayoutDashboard,
    LogOut,
    Settings,
} from 'lucide-react'
import type { ReactNode } from 'react'
import LogoutAction from '@/components/LogoutAction'

type NavItemProps = {
    href: string
    icon: React.ReactNode
    label: string
    active?: boolean
}

export default function DashboardLayout({ children }: { children: ReactNode }) {
    const pathname = usePathname()

    return (
        <div className="flex min-h-screen bg-[#FAF9F6]">
            <aside className="hidden w-64 shrink-0 border-r border-[#E5E5E5] bg-[#FAF9F6] md:flex md:flex-col">
                <div className="flex h-16 items-center border-b border-[#E5E5E5] px-6">
                    <Link href="/dashboard" className="text-lg font-serif italic font-medium text-[#111111]">
                        PanelMind
                    </Link>
                </div>

                <nav className="flex-1 space-y-1 px-4 py-6">
                    <NavItem href="/dashboard" icon={<LayoutDashboard size={18} />} label="工作台" active={pathname === '/dashboard'} />
                    <NavItem
                        href="/dashboard/questions"
                        icon={<BookOpen size={18} />}
                        label="题库中心"
                        active={pathname === '/dashboard/questions' || pathname.startsWith('/dashboard/questions/')}
                    />
                    <NavItem href="/history" icon={<History size={18} />} label="历史记录" active={pathname === '/history' || pathname.startsWith('/history/')} />
                    <NavItem href="/replay" icon={<Film size={18} />} label="面试复盘" active={pathname === '/replay' || pathname.startsWith('/replay/')} />
                    <NavItem href="/insights" icon={<BarChart3 size={18} />} label="近期总结" active={pathname === '/insights' || pathname.startsWith('/insights/')} />
                </nav>

                <div className="space-y-1 border-t border-[#E5E5E5] p-4">
                    <NavItem href="/settings" icon={<Settings size={18} />} label="设置" active={pathname === '/settings' || pathname.startsWith('/settings/')} />
                    <LogoutAction className="relative flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium text-[#666666] transition-colors hover:bg-[#F1F0EC] hover:text-[#111111]">
                        <LogOut size={18} />
                        <span>退出登录</span>
                    </LogoutAction>
                </div>
            </aside>

            <main className="flex h-screen flex-1 flex-col overflow-hidden">{children}</main>
        </div>
    )
}

function NavItem({ href, icon, label, active }: NavItemProps) {
    return (
        <Link
            href={href}
            className={`relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active ? 'text-[#111111]' : 'text-[#666666] hover:text-[#111111]'
            }`}
        >
            {active ? (
                <motion.div
                    layoutId="sidebar-active-indicator"
                    className="absolute inset-0 rounded-lg bg-[#EBE9E0]"
                    transition={{ type: 'spring', stiffness: 350, damping: 30 }}
                />
            ) : null}
            <span className="relative z-10 flex items-center gap-3">
                {icon}
                {label}
            </span>
        </Link>
    )
}

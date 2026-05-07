'use client'

import Link from 'next/link'
import type { ComponentType, ReactNode } from 'react'
import { Bell, ChevronRight, KeyRound, MoonStar, UserCircle2 } from 'lucide-react'
import PersistentSidebar from '@/components/PersistentSidebar'
import ThemeToggleSwitch from '@/components/ThemeToggleSwitch'

type SettingCardProps = {
    icon: ComponentType<{ className?: string }>
    title: string
    description: string
    href?: string
    actionText?: string
    children?: ReactNode
}

function SettingCard({ icon: Icon, title, description, href, actionText, children }: SettingCardProps) {
    return (
        <article className="rounded-2xl border border-[#E5E5E5] bg-white p-5 shadow-sm transition hover:shadow-md dark:border-[#2d3542] dark:bg-[#181c24]">
            <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] dark:border-[#2d3542] dark:bg-[#101217]">
                <Icon className="h-5 w-5 text-[#111111] dark:text-[#f4f7fb]" />
            </div>
            <h3 className="text-base font-semibold text-[#111111] dark:text-[#f4f7fb]">{title}</h3>
            <p className="mt-2 text-sm leading-6 text-[#666666] dark:text-[#bcc5d3]">{description}</p>
            {children ? <div className="mt-4">{children}</div> : null}
            {href && actionText ? (
                <Link
                    href={href}
                    className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-[#111111] transition hover:text-[#333333] dark:text-[#f4f7fb] dark:hover:text-white"
                >
                    {actionText}
                    <ChevronRight className="h-4 w-4" />
                </Link>
            ) : null}
        </article>
    )
}

export default function SettingsPage() {
    return (
        <div className="flex min-h-screen bg-[#FAF9F6] dark:bg-[#101217]">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-5xl px-6 py-8">
                    <section className="rounded-3xl border border-[#E5E5E5] bg-[#FAF9F6] p-8 shadow-sm dark:border-[#2d3542] dark:bg-[#101217]">
                        <p className="text-xs font-medium uppercase tracking-[0.18em] text-[#999999] dark:text-[#8e98aa]">系统设置</p>
                        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#111111] dark:text-[#f4f7fb] sm:text-4xl">
                            PanelMind 系统设置
                        </h1>
                    </section>

                    <section className="mt-6 grid gap-4 md:grid-cols-2">
                        <SettingCard
                            icon={UserCircle2}
                            title="个人资料"
                            description="维护昵称、头像、目标岗位和简历信息，帮助系统给出更贴合你的训练建议。"
                            href="/me"
                            actionText="前往编辑个人资料"
                        />
                        <SettingCard
                            icon={Bell}
                            title="通知提醒"
                            description="管理 24 小时未训练提醒、连续训练提醒和周计划到期提醒，并同步到右上角通知中心。"
                            href="/settings/notifications"
                            actionText="配置提醒方式"
                        />
                    </section>

                    <section className="mt-4 grid gap-4 md:grid-cols-2">
                        <SettingCard
                            icon={MoonStar}
                            title="主题与外观模式"
                            description="切换浅色或深色外观，让界面更舒适。"
                        >
                            <ThemeToggleSwitch />
                        </SettingCard>
                        <SettingCard
                            icon={KeyRound}
                            title="账号安全"
                            description="修改登录密码、管理登录状态，保护你的账号安全。"
                            href="/settings/account"
                            actionText="管理账号安全"
                        />
                    </section>
                </div>
            </main>
        </div>
    )
}

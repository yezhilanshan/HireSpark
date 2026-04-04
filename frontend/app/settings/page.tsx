'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { Bell, ChevronRight, MoonStar, ShieldCheck, SlidersHorizontal, UserCircle2 } from 'lucide-react'
import PersistentSidebar from '@/components/PersistentSidebar'

export default function SettingsPage() {
    const [mounted, setMounted] = useState(false)

    useEffect(() => {
        setMounted(true)
    }, [])

    return (
        <div className="flex min-h-screen">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-5xl px-6 py-8">
                    <section className="rounded-3xl border border-[#E5E5E5] bg-[#FAF9F6] p-8 shadow-sm">
                        <p className="text-xs font-medium uppercase tracking-[0.18em] text-[#999999]">System Settings</p>
                        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#111111] sm:text-4xl">工作台设置</h1>
                        <p className="mt-2 text-sm text-[#666666]">这里聚合显示相关配置入口，后续可按模块逐步扩展。</p>
                    </section>

                    <section className="mt-6 grid gap-4 md:grid-cols-2">
                        <SettingCard
                            icon={UserCircle2}
                            title="个人资料"
                            description="编辑目标岗位、简历与联系方式等候选人信息。"
                            href="/me"
                            actionText="前往我的资料"
                        />
                        <SettingCard
                            icon={MoonStar}
                            title="外观与主题"
                            description={mounted ? '可在左侧栏底部即时切换明暗主题。' : '正在加载当前主题偏好...'}
                            href="/"
                            actionText="返回工作台"
                        />
                        <SettingCard
                            icon={Bell}
                            title="通知偏好"
                            description="预留邮件与站内通知配置位，便于后续接入提醒能力。"
                        />
                        <SettingCard
                            icon={ShieldCheck}
                            title="隐私与安全"
                            description="预留账号安全和数据保留策略配置位。"
                        />
                    </section>

                    <section className="mt-6 rounded-2xl border border-[#E5E5E5] bg-white p-5 shadow-sm">
                        <div className="flex items-center gap-2">
                            <SlidersHorizontal className="h-4 w-4 text-[#111111]" />
                            <h2 className="text-lg font-medium text-[#111111]">说明</h2>
                        </div>
                        <p className="mt-2 text-sm leading-6 text-[#666666]">
                            当前版本将"设置"与"我的资料"进行信息架构拆分，避免重复入口混淆；实际配置能力可以按功能迭代逐项补齐。
                        </p>
                    </section>
                </div>
            </main>
        </div>
    )
}

function SettingCard({
    icon: Icon,
    title,
    description,
    href,
    actionText,
}: {
    icon: React.ComponentType<{ className?: string }>
    title: string
    description: string
    href?: string
    actionText?: string
}) {
    return (
        <article className="rounded-2xl border border-[#E5E5E5] bg-white p-5 shadow-sm">
            <div className="mb-3 inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[#E5E5E5] bg-[#FAF9F6]">
                <Icon className="h-4 w-4 text-[#111111]" />
            </div>
            <h3 className="text-base font-semibold text-[#111111]">{title}</h3>
            <p className="mt-2 text-sm leading-6 text-[#666666]">{description}</p>
            {href && actionText ? (
                <Link
                    href={href}
                    className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-[#111111] transition hover:text-[#333333]"
                >
                    {actionText}
                    <ChevronRight className="h-4 w-4" />
                </Link>
            ) : null}
        </article>
    )
}

'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { ArrowLeft, BellRing, Loader2, Save } from 'lucide-react'
import PersistentSidebar from '@/components/PersistentSidebar'
import { getBackendBaseUrl } from '@/lib/backend'

const BACKEND_API_BASE = getBackendBaseUrl()

type NotificationSettings = {
    user_id: string
    in_app_enabled: boolean
    inactivity_24h_enabled: boolean
    streak_enabled: boolean
    weekly_plan_due_enabled: boolean
}

const DEFAULT_SETTINGS: NotificationSettings = {
    user_id: 'default',
    in_app_enabled: true,
    inactivity_24h_enabled: true,
    streak_enabled: true,
    weekly_plan_due_enabled: true,
}

function ToggleRow({
    title,
    description,
    checked,
    disabled,
    onChange,
}: {
    title: string
    description: string
    checked: boolean
    disabled?: boolean
    onChange: (next: boolean) => void
}) {
    return (
        <div className="flex items-start justify-between gap-4 rounded-2xl border border-[#E5E5E5] bg-white px-5 py-4 dark:border-[#2d3542] dark:bg-[#181c24]">
            <div>
                <h3 className="text-sm font-semibold text-[#111111] dark:text-[#f4f7fb]">{title}</h3>
                <p className="mt-1 text-sm leading-6 text-[#666666] dark:text-[#bcc5d3]">{description}</p>
            </div>
            <button
                type="button"
                disabled={disabled}
                onClick={() => onChange(!checked)}
                className={[
                    'relative mt-1 inline-flex h-7 w-12 shrink-0 items-center rounded-full transition',
                    checked ? 'bg-[#111111] dark:bg-[#f4f7fb]' : 'bg-[#D8D2C4] dark:bg-[#3b4452]',
                    disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer',
                ].join(' ')}
                aria-pressed={checked}
            >
                <span
                    className={[
                        'inline-block h-5 w-5 rounded-full bg-white shadow-sm transition dark:bg-[#101217]',
                        checked ? 'translate-x-6' : 'translate-x-1',
                    ].join(' ')}
                />
            </button>
        </div>
    )
}

export default function NotificationSettingsPage() {
    const [settings, setSettings] = useState<NotificationSettings>(DEFAULT_SETTINGS)
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [statusText, setStatusText] = useState('')

    useEffect(() => {
        let cancelled = false

        const load = async () => {
            setLoading(true)
            setStatusText('')
            try {
                const authResponse = await fetch('/api/auth/me', { cache: 'no-store' })
                const authData = await authResponse.json().catch(() => ({}))
                const userId = String(authData?.user?.email || 'default').trim().toLowerCase() || 'default'

                const response = await fetch(
                    `${BACKEND_API_BASE}/api/user/notification-settings?user_id=${encodeURIComponent(userId)}`,
                    { cache: 'no-store' }
                )
                const data = await response.json().catch(() => ({}))

                if (!response.ok || !data?.success) {
                    throw new Error(data?.error || '提醒设置加载失败')
                }

                if (cancelled) return
                setSettings({
                    ...DEFAULT_SETTINGS,
                    ...data.settings,
                    user_id: userId,
                })
            } catch (error) {
                if (cancelled) return
                setStatusText(error instanceof Error ? error.message : '提醒设置加载失败')
            } finally {
                if (!cancelled) setLoading(false)
            }
        }

        void load()
        return () => {
            cancelled = true
        }
    }, [])

    const saveSettings = async () => {
        setSaving(true)
        setStatusText('')
        try {
            const response = await fetch(`${BACKEND_API_BASE}/api/user/notification-settings`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings),
            })
            const data = await response.json().catch(() => ({}))
            if (!response.ok || !data?.success) {
                throw new Error(data?.error || '提醒设置保存失败')
            }
            setSettings((prev) => ({ ...prev, ...data.settings }))
            setStatusText('提醒设置已保存')
        } catch (error) {
            setStatusText(error instanceof Error ? error.message : '提醒设置保存失败')
        } finally {
            setSaving(false)
        }
    }

    return (
        <div className="flex min-h-screen bg-[#FAF9F6] dark:bg-[#101217]">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-4xl px-6 py-8">
                    <div className="mb-4">
                        <Link
                            href="/settings"
                            className="inline-flex items-center gap-2 rounded-lg border border-[#E5E5E5] bg-white px-3 py-2 text-sm font-medium text-[#111111] transition hover:bg-[#F5F5F5] dark:border-[#2d3542] dark:bg-[#181c24] dark:text-[#f4f7fb] dark:hover:bg-[#222832]"
                        >
                            <ArrowLeft className="h-4 w-4" />
                            返回设置
                        </Link>
                    </div>

                    <section className="rounded-3xl border border-[#E5E5E5] bg-[#FAF9F6] p-8 shadow-sm dark:border-[#2d3542] dark:bg-[#101217]">
                        <div className="flex items-start gap-4">
                            <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-[#E5E5E5] bg-white dark:border-[#2d3542] dark:bg-[#181c24]">
                                <BellRing className="h-6 w-6 text-[#111111] dark:text-[#f4f7fb]" />
                            </div>
                            <div>
                                <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#111111] dark:text-[#f4f7fb]">
                                    通知与训练提醒
                                </h1>
                                <p className="mt-2 text-sm leading-6 text-[#666666] dark:text-[#bcc5d3]">
                                    我们先提供站内提醒版本，重点覆盖未训练、连续训练和周计划到期这三种最影响留存与执行节奏的场景。
                                </p>
                            </div>
                        </div>
                    </section>

                    <section className="mt-6 space-y-4">
                        <ToggleRow
                            title="开启站内提醒"
                            description="关闭后，工作台中的所有行为提醒卡片都会一起隐藏。"
                            checked={settings.in_app_enabled}
                            disabled={loading || saving}
                            onChange={(next) => setSettings((prev) => ({ ...prev, in_app_enabled: next }))}
                        />
                        <ToggleRow
                            title="24 小时未训练提醒"
                            description="如果超过 24 小时没有新的训练记录，工作台会提示你尽快恢复节奏。"
                            checked={settings.inactivity_24h_enabled}
                            disabled={loading || saving || !settings.in_app_enabled}
                            onChange={(next) => setSettings((prev) => ({ ...prev, inactivity_24h_enabled: next }))}
                        />
                        <ToggleRow
                            title="连续 3 天训练连击"
                            description="当你连续训练达到 3 天及以上时，工作台会显示连击提醒，帮助你保持惯性。"
                            checked={settings.streak_enabled}
                            disabled={loading || saving || !settings.in_app_enabled}
                            onChange={(next) => setSettings((prev) => ({ ...prev, streak_enabled: next }))}
                        />
                        <ToggleRow
                            title="周计划到期未验收提醒"
                            description="如果本周训练计划临近到期或已到期但仍有任务未完成，系统会提醒你优先处理。"
                            checked={settings.weekly_plan_due_enabled}
                            disabled={loading || saving || !settings.in_app_enabled}
                            onChange={(next) => setSettings((prev) => ({ ...prev, weekly_plan_due_enabled: next }))}
                        />
                    </section>

                    <div className="mt-6 flex items-center justify-between gap-4 rounded-2xl border border-[#E5E5E5] bg-white px-5 py-4 dark:border-[#2d3542] dark:bg-[#181c24]">
                        <div className="min-h-6 text-sm text-[#666666] dark:text-[#bcc5d3]">
                            {loading ? '正在加载提醒设置...' : statusText || '你可以随时调整提醒强度，系统会按当前登录用户保存。'}
                        </div>
                        <button
                            type="button"
                            disabled={loading || saving}
                            onClick={saveSettings}
                            className="inline-flex items-center gap-2 rounded-xl bg-[#111111] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#222222] disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                            保存设置
                        </button>
                    </div>
                </div>
            </main>
        </div>
    )
}

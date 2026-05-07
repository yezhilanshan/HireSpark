'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowRight, Bell, BellRing, Loader2 } from 'lucide-react'
import { getBackendBaseUrl } from '@/lib/backend'

const BACKEND_API_BASE = getBackendBaseUrl()

type ReminderItem = {
    id: string
    type: string
    tone: 'info' | 'warning' | 'success' | 'danger' | string
    title: string
    message: string
    cta_label?: string
    cta_href?: string
}

type ReminderSummary = {
    last_training_at?: string
    hours_since_training?: number | null
    current_streak_days?: number
    weekly_plan_pending_count?: number
    weekly_plan_due_at?: string
}

type NotificationCenterProps = {
    mode?: 'floating' | 'inline'
}

function reminderToneClasses(tone?: string): string {
    if (tone === 'success') return 'border-emerald-200 bg-emerald-50 text-emerald-800'
    if (tone === 'warning') return 'border-amber-200 bg-amber-50 text-amber-800'
    if (tone === 'danger') return 'border-red-200 bg-red-50 text-red-800'
    return 'border-sky-200 bg-sky-50 text-sky-800'
}

export default function NotificationCenter({ mode = 'floating' }: NotificationCenterProps) {
    const router = useRouter()
    const containerRef = useRef<HTMLDivElement | null>(null)
    const [open, setOpen] = useState(false)
    const [loading, setLoading] = useState(false)
    const [reminders, setReminders] = useState<ReminderItem[]>([])
    const [summary, setSummary] = useState<ReminderSummary | null>(null)

    useEffect(() => {
        if (!open) return

        const handlePointerDown = (event: MouseEvent) => {
            if (!containerRef.current?.contains(event.target as Node)) {
                setOpen(false)
            }
        }

        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                setOpen(false)
            }
        }

        document.addEventListener('mousedown', handlePointerDown)
        document.addEventListener('keydown', handleEscape)

        return () => {
            document.removeEventListener('mousedown', handlePointerDown)
            document.removeEventListener('keydown', handleEscape)
        }
    }, [open])

    useEffect(() => {
        if (!open) return

        let cancelled = false

        const loadNotifications = async () => {
            setLoading(true)
            try {
                const authResponse = await fetch('/api/auth/me', { cache: 'no-store' })
                const authData = await authResponse.json().catch(() => ({}))
                const userId = String(authData?.user?.email || 'default').trim().toLowerCase() || 'default'

                const response = await fetch(
                    `${BACKEND_API_BASE}/api/user/reminders?user_id=${encodeURIComponent(userId)}`,
                    { cache: 'no-store' }
                )
                const data = await response.json().catch(() => ({}))
                if (!response.ok || !data?.success || cancelled) return

                setReminders(Array.isArray(data?.reminders) ? data.reminders : [])
                setSummary(data?.summary && typeof data.summary === 'object' ? data.summary : null)
            } catch {
                if (cancelled) return
                setReminders([])
                setSummary(null)
            } finally {
                if (!cancelled) setLoading(false)
            }
        }

        void loadNotifications()

        return () => {
            cancelled = true
        }
    }, [open])

    const unreadCount = reminders.length
    const badgeText = unreadCount > 9 ? '9+' : `${unreadCount}`
    const summaryText = useMemo(() => {
        if (summary?.current_streak_days) {
            return `你已连续训练 ${summary.current_streak_days} 天`
        }
        if (summary?.weekly_plan_pending_count) {
            return `还有 ${summary.weekly_plan_pending_count} 项周计划待处理`
        }
        return '最近的训练提醒会集中展示在这里'
    }, [summary])

    const buttonClassName =
        mode === 'inline'
            ? 'relative inline-flex h-11 w-11 items-center justify-center rounded-xl border border-slate-300/80 bg-white/85 text-slate-700 shadow-lg backdrop-blur transition hover:-translate-y-0.5 hover:bg-white dark:border-slate-700 dark:bg-slate-900/80 dark:text-slate-100 dark:hover:bg-slate-900'
            : 'relative inline-flex h-12 w-12 items-center justify-center rounded-xl border border-slate-300/80 bg-white/85 text-slate-700 shadow-xl backdrop-blur transition hover:-translate-y-0.5 hover:bg-white dark:border-slate-700 dark:bg-slate-900/80 dark:text-slate-100 dark:hover:bg-slate-900'

    const panelClassName =
        mode === 'inline'
            ? 'absolute right-0 top-[calc(100%+12px)] z-50 w-[360px] max-w-[calc(100vw-24px)] rounded-3xl border border-[#E5E5E5] bg-white p-4 shadow-[0_24px_64px_rgba(17,17,17,0.18)] dark:border-[#2d3542] dark:bg-[#181c24]'
            : 'absolute right-0 top-[calc(100%+12px)] z-50 w-[360px] max-w-[calc(100vw-24px)] rounded-3xl border border-[#E5E5E5] bg-white p-4 shadow-[0_24px_64px_rgba(17,17,17,0.18)] dark:border-[#2d3542] dark:bg-[#181c24]'

    const wrapperClassName = mode === 'inline' ? 'relative' : 'fixed right-4 top-4 z-50'

    return (
        <div ref={containerRef} className={wrapperClassName}>
            <button
                type="button"
                onClick={() => setOpen((prev) => !prev)}
                className={buttonClassName}
                title="通知消息"
                aria-label="查看通知消息"
            >
                <Bell className="h-5 w-5" />
                {unreadCount > 0 ? (
                    <span className="absolute -right-1 -top-1 inline-flex min-w-5 items-center justify-center rounded-full bg-[#111111] px-1.5 py-0.5 text-[10px] font-semibold text-white dark:bg-[#f4f7fb] dark:text-[#101217]">
                        {badgeText}
                    </span>
                ) : null}
            </button>

            {open ? (
                <div className={panelClassName}>
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <p className="text-base font-semibold text-[#111111] dark:text-[#f4f7fb]">最近通知</p>
                            <p className="mt-1 text-xs leading-5 text-[#7B746A] dark:text-[#9aa7bd]">{summaryText}</p>
                        </div>
                        <span className="rounded-full bg-[#F3EFE6] px-2.5 py-1 text-xs font-medium text-[#6E675D] dark:bg-[#252b36] dark:text-[#d2dae8]">
                            {unreadCount} 条
                        </span>
                    </div>

                    <div className="mt-4 max-h-[420px] space-y-3 overflow-y-auto pr-1">
                        {loading ? (
                            <div className="flex items-center justify-center gap-2 rounded-2xl border border-[#E5E5E5] px-4 py-6 text-sm text-[#666666] dark:border-[#2d3542] dark:text-[#bcc5d3]">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                <span>正在加载通知...</span>
                            </div>
                        ) : reminders.length === 0 ? (
                            <div className="rounded-2xl border border-dashed border-[#D8D2C4] px-4 py-6 text-center text-sm leading-6 text-[#666666] dark:border-[#3b4452] dark:text-[#bcc5d3]">
                                暂时没有新的提醒消息。
                            </div>
                        ) : (
                            reminders.map((item) => (
                                <div
                                    key={item.id}
                                    className={`rounded-2xl border px-4 py-3 ${reminderToneClasses(item.tone)} dark:border-transparent`}
                                >
                                    <div className="flex items-start gap-3">
                                        <BellRing className="mt-0.5 h-4 w-4 shrink-0" />
                                        <div className="min-w-0 flex-1">
                                            <p className="text-sm font-semibold">{item.title}</p>
                                            <p className="mt-1 text-sm leading-6 opacity-90">{item.message}</p>
                                            {item.cta_href && item.cta_label ? (
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        setOpen(false)
                                                        router.push(item.cta_href || '/dashboard')
                                                    }}
                                                    className="mt-3 inline-flex items-center gap-1 text-sm font-medium underline underline-offset-4"
                                                >
                                                    {item.cta_label}
                                                    <ArrowRight className="h-3.5 w-3.5" />
                                                </button>
                                            ) : null}
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            ) : null}
        </div>
    )
}

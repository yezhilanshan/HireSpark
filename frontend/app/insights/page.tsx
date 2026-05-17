'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
    AlertCircle,
    ArrowRight,
    BarChart3,
    Briefcase,
    Gauge,
    ShieldCheck,
    Sparkles,
    Target,
    TrendingUp,
} from 'lucide-react'
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Legend,
    Line,
    LineChart,
    Pie,
    PieChart,
    PolarAngleAxis,
    PolarGrid,
    Radar,
    RadarChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts'
import PersistentSidebar from '@/components/PersistentSidebar'
import { fetchWithTimeout, getBackendBaseUrl } from '@/lib/backend'
import { readPageCache, writePageCache } from '@/lib/page-cache'

const BACKEND_API_BASE = getBackendBaseUrl()
const ROUND_COLORS = ['#111111', '#4C6A8A', '#B67A2D', '#7A8E63']
const FIT_GAUGE_COLORS = ['#111111', '#E8E2D7']
const INSIGHTS_CACHE_KEY = 'zhiyuexingchen.page.insights.v1'
const INSIGHTS_CACHE_TTL_MS = 1000 * 60 * 15

type RecentMetricItem = {
    interview_id: string
    created_at: string
    duration_seconds: number
    round_type: string
    round_label: string
    position: string
    position_label: string
    score: number | null
    risk_score: number | null
    stability_score: number | null
    content_score: number | null
    delivery_score: number | null
    presence_score: number | null
    job_match_score: number | null
    report_url: string
}

type RoundCoverageItem = {
    round_type: string
    label: string
    count: number
    status: 'ready' | 'insufficient'
    avg_score: number | null
}

type RadarDimension = {
    key: string
    label: string
    score: number
}

type FitBreakdownItem = {
    key: string
    label: string
    score: number | null
}

type PrimaryGap = {
    title?: string
    description?: string
    reason?: string
    summary?: string
    manifestations?: string[]
    impact?: string
    focus?: string
    impacted_rounds?: string[]
    evidence?: string[]
}

type GrowthAdviceItem = {
    title?: string
    advice?: string
}

type RecommendedReview = {
    interview_id: string
    round_label: string
    created_at: string
    score: number | null
    reason: string
    report_url: string
}

type InsightsSummaryPayload = {
    success: boolean
    recent_metrics: {
        items: RecentMetricItem[]
        averages: {
            score?: number | null
            stability?: number | null
            risk?: number | null
        }
        axis_averages: {
            content?: number | null
            delivery?: number | null
            presence?: number | null
        }
        delta_from_previous?: number | null
    }
    weekly_distribution: Array<{ name: string; value: number }>
    cross_round_profile: {
        sample_count: number
        covered_round_count: number
        target_position: string
        target_position_label: string
        round_coverage: RoundCoverageItem[]
        radar_dimensions: RadarDimension[]
        fit_score: number
        fit_breakdown: FitBreakdownItem[]
        primary_gap_candidate?: PrimaryGap
        recommended_review?: RecommendedReview | null
    }
    ai_summary: {
        profile_summary?: string
        fit_summary?: {
            summary?: string
            blocker?: string
        }
        primary_gap?: PrimaryGap
        growth_advice?: GrowthAdviceItem[]
    }
    ai_summary_meta?: {
        status?: string
        required?: boolean
        timeout_seconds?: number
    }
    error?: string
}

type TrainingTask = {
    task_id: string
    title: string
    round_type: string
    round_label: string
    position: string
    position_label: string
    difficulty: string
    focus_label?: string
    goal_score: number
    status: string
    status_label: string
    last_score?: number | null
}

type WeeklyTrainingPlanPayload = {
    success: boolean
    week_start_date: string
    week_end_date: string
    plan: {
        plan_id: string
        target_position: string
        target_position_label: string
        status: string
        status_label: string
    }
    tasks: TrainingTask[]
    stage_summary: {
        planned: number
        training: number
        validation: number
        reflow: number
        completed: number
        total: number
    }
    error?: string
}

function formatNumber(value?: number | null, digits = 1): string {
    return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : '--'
}

function formatScore(value?: number | null): string {
    return formatNumber(value, 1)
}

function formatRiskLabel(value?: number | null): string {
    if (!Number.isFinite(Number(value))) return '暂无风险数据'
    if (Number(value) >= 60) return '风险偏高'
    if (Number(value) >= 35) return '风险中等'
    return '风险可控'
}

function formatDuration(seconds?: number | null): string {
    const safe = Math.max(0, Math.round(Number(seconds || 0)))
    const min = Math.floor(safe / 60)
    const sec = safe % 60
    if (min <= 0) return `${sec}秒`
    return `${min}分${sec}秒`
}

function formatDate(value?: string): string {
    if (!value) return '--'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return value
    return new Intl.DateTimeFormat('zh-CN', {
        timeZone: 'Asia/Shanghai',
        month: 'numeric',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23',
    }).format(date)
}

function buildTrendData(items: RecentMetricItem[]) {
    return items.map((item) => ({
        label: formatDate(item.created_at),
        score: item.score,
        stability: item.stability_score,
        risk: item.risk_score,
    }))
}

function buildAxisData(axisAverages: InsightsSummaryPayload['recent_metrics']['axis_averages']) {
    return [
        { name: '内容轴', score: axisAverages.content ?? null, fill: '#4C6A8A' },
        { name: '表达轴', score: axisAverages.delivery ?? null, fill: '#7A8E63' },
        { name: '镜头轴', score: axisAverages.presence ?? null, fill: '#B67A2D' },
    ]
}

async function safeReadJson<T>(response: Response): Promise<T | null> {
    try {
        return (await response.json()) as T
    } catch {
        return null
    }
}

function normalizeRoundType(raw?: string): 'technical' | 'project' | 'system_design' | 'hr' {
    const value = String(raw || '').trim().toLowerCase()
    if (value === 'project') return 'project'
    if (value === 'system_design' || value === 'system-design' || value === 'system design') return 'system_design'
    if (value === 'hr') return 'hr'
    return 'technical'
}

function normalizeDifficulty(raw?: string): 'easy' | 'medium' | 'hard' {
    const value = String(raw || '').trim().toLowerCase()
    if (value === 'easy') return 'easy'
    if (value === 'hard') return 'hard'
    return 'medium'
}

function statusClassName(status: string): string {
    const normalized = String(status || '').trim().toLowerCase()
    if (normalized === 'completed') return 'bg-[#EAF5ED] text-[#2F6B45]'
    if (normalized === 'validation') return 'bg-[#E8EEF7] text-[#2B4F7A]'
    if (normalized === 'training') return 'bg-[#FFF4DF] text-[#8A5A11]'
    if (normalized === 'reflow') return 'bg-[#FCEBE9] text-[#9D3A2E]'
    if (normalized === 'rolled_over') return 'bg-[#F2F2F0] text-[#666666]'
    return 'bg-[#F2F2F0] text-[#666666]'
}

function shouldShowStartTraining(status: string): boolean {
    const normalized = String(status || '').trim().toLowerCase()
    return normalized === 'planned' || normalized === 'training' || normalized === 'reflow'
}

function shouldShowStartValidation(status: string): boolean {
    const normalized = String(status || '').trim().toLowerCase()
    return normalized === 'training' || normalized === 'validation'
}

function shouldShowMarkResult(status: string): boolean {
    const normalized = String(status || '').trim().toLowerCase()
    return normalized === 'validation'
}

export default function InsightsPage() {
    const router = useRouter()
    const cachedSummary = typeof window === 'undefined'
        ? null
        : readPageCache<InsightsSummaryPayload>(INSIGHTS_CACHE_KEY, INSIGHTS_CACHE_TTL_MS)
    const initialCache = cachedSummary?.ai_summary_meta?.status === 'generated' ? cachedSummary : null
    const hasCachedSummary = Boolean(initialCache)

    const [loading, setLoading] = useState(!initialCache)
    const [error, setError] = useState('')
    const [summary, setSummary] = useState<InsightsSummaryPayload | null>(initialCache)
    const [weeklyPlanLoading, setWeeklyPlanLoading] = useState(true)
    const [weeklyPlanError, setWeeklyPlanError] = useState('')
    const [weeklyPlan, setWeeklyPlan] = useState<WeeklyTrainingPlanPayload | null>(null)
    const [actingTaskId, setActingTaskId] = useState('')
    const [reflowBusy, setReflowBusy] = useState(false)

    const loadWeeklyPlan = useCallback(async () => {
        try {
            setWeeklyPlanLoading(true)
            setWeeklyPlanError('')
            const res = await fetchWithTimeout(`${BACKEND_API_BASE}/api/training/weekly-plan?user_id=default`, { cache: 'no-store' }, 8000)
            const data = await safeReadJson<WeeklyTrainingPlanPayload>(res)
            if (!res.ok || !data?.success) {
                throw new Error(data?.error || '获取本周训练计划失败')
            }
            setWeeklyPlan(data)
        } catch (loadError) {
            setWeeklyPlanError(loadError instanceof Error ? loadError.message : '获取本周训练计划失败')
        } finally {
            setWeeklyPlanLoading(false)
        }
    }, [])

    useEffect(() => {
        const load = async () => {
            try {
                if (!hasCachedSummary) {
                    setLoading(true)
                }
                setError('')
                const res = await fetchWithTimeout(`${BACKEND_API_BASE}/api/insights/summary`, { cache: 'no-store' }, 45000)
                const data = await safeReadJson<InsightsSummaryPayload>(res)
                if (!res.ok || !data?.success) {
                    throw new Error(data?.error || '获取最近面试总览失败')
                }
                setSummary(data)
                writePageCache<InsightsSummaryPayload>(INSIGHTS_CACHE_KEY, data)
            } catch (loadError) {
                if (hasCachedSummary) {
                    setError('综合画像更新失败，已展示缓存数据。')
                } else {
                    setError(loadError instanceof Error ? loadError.message : '获取最近面试总览失败')
                }
            } finally {
                setLoading(false)
            }
        }

        void load()
    }, [])

    useEffect(() => {
        void loadWeeklyPlan()
    }, [loadWeeklyPlan])

    const handleStartTraining = useCallback(async (taskId: string) => {
        const normalizedTaskId = String(taskId || '').trim()
        if (!normalizedTaskId) {
            return
        }
        try {
            setActingTaskId(normalizedTaskId)
            setWeeklyPlanError('')
            const res = await fetch(`${BACKEND_API_BASE}/api/training/tasks/${normalizedTaskId}/start-training`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: 'default' }),
            })
            const data = await safeReadJson<{ success: boolean; error?: string; navigate_url?: string }>(res)
            if (!res.ok || !data?.success) {
                throw new Error(data?.error || '开启训练失败')
            }
            router.push(data?.navigate_url || '/dashboard/questions')
        } catch (actionError) {
            setWeeklyPlanError(actionError instanceof Error ? actionError.message : '开启训练失败')
        } finally {
            setActingTaskId('')
        }
    }, [router])

    const handleStartValidation = useCallback(async (taskId: string) => {
        const normalizedTaskId = String(taskId || '').trim()
        if (!normalizedTaskId) {
            return
        }
        try {
            setActingTaskId(normalizedTaskId)
            setWeeklyPlanError('')
            const res = await fetch(`${BACKEND_API_BASE}/api/training/tasks/${normalizedTaskId}/start-validation`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: 'default' }),
            })
            const data = await safeReadJson<{
                success: boolean
                error?: string
                navigate_url?: string
                interview_config?: {
                    round?: string
                    position?: string
                    difficulty?: string
                    trainingTaskId?: string
                    trainingMode?: string
                    auto_end_min_questions?: number
                    auto_end_max_questions?: number
                }
            }>(res)
            if (!res.ok || !data?.success) {
                throw new Error(data?.error || '开启验收失败')
            }

            const nextConfig = data?.interview_config || {}
            sessionStorage.setItem('interview_config', JSON.stringify({
                round: normalizeRoundType(nextConfig.round),
                position: String(nextConfig.position || '').trim().toLowerCase() || 'java_backend',
                difficulty: normalizeDifficulty(nextConfig.difficulty),
                trainingTaskId: String(nextConfig.trainingTaskId || '').trim(),
                trainingMode: String(nextConfig.trainingMode || '').trim() || 'coach_drill',
                auto_end_min_questions: Number(nextConfig.auto_end_min_questions || 3),
                auto_end_max_questions: Number(nextConfig.auto_end_max_questions || 3),
            }))

            router.push(data?.navigate_url || '/interview')
        } catch (actionError) {
            setWeeklyPlanError(actionError instanceof Error ? actionError.message : '开启验收失败')
        } finally {
            setActingTaskId('')
        }
    }, [router])

    const handleReflowPending = useCallback(async (): Promise<number> => {
        if (!weeklyPlan?.week_start_date) {
            return 0
        }
        try {
            setReflowBusy(true)
            setWeeklyPlanError('')
            const res = await fetch(`${BACKEND_API_BASE}/api/training/tasks/reflow`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: 'default',
                    week_start_date: weeklyPlan.week_start_date,
                }),
            })
            const data = await safeReadJson<{ success: boolean; error?: string; created_count?: number }>(res)
            if (!res.ok || !data?.success) {
                throw new Error(data?.error || '执行回流失败')
            }
            await loadWeeklyPlan()
            return Number(data?.created_count || 0)
        } catch (actionError) {
            setWeeklyPlanError(actionError instanceof Error ? actionError.message : '执行回流失败')
            return 0
        } finally {
            setReflowBusy(false)
        }
    }, [loadWeeklyPlan, weeklyPlan?.week_start_date])

    const handleMarkResult = useCallback(async (taskId: string, passed: boolean) => {
        const normalizedTaskId = String(taskId || '').trim()
        if (!normalizedTaskId) {
            return
        }
        try {
            setActingTaskId(normalizedTaskId)
            setWeeklyPlanError('')
            const res = await fetch(`${BACKEND_API_BASE}/api/training/tasks/${normalizedTaskId}/mark-result`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    passed,
                    notes: passed ? 'manual_mark_passed' : 'manual_mark_failed',
                }),
            })
            const data = await safeReadJson<{ success: boolean; error?: string }>(res)
            if (!res.ok || !data?.success) {
                throw new Error(data?.error || '记录验收结果失败')
            }
            if (!passed) {
                await handleReflowPending()
            } else {
                await loadWeeklyPlan()
            }
        } catch (actionError) {
            setWeeklyPlanError(actionError instanceof Error ? actionError.message : '记录验收结果失败')
        } finally {
            setActingTaskId('')
        }
    }, [handleReflowPending, loadWeeklyPlan])

    const recentItems = summary?.recent_metrics.items || []
    const trendData = useMemo(() => buildTrendData(recentItems), [recentItems])
    const axisData = useMemo(() => buildAxisData(summary?.recent_metrics.axis_averages || {}), [summary])
    const radarDimensions = summary?.cross_round_profile.radar_dimensions || []
    const fitBreakdown = summary?.cross_round_profile.fit_breakdown || []
    const recommendedReview = summary?.cross_round_profile.recommended_review
    const aiPrimaryGap = summary?.ai_summary.primary_gap || summary?.cross_round_profile.primary_gap_candidate
    const fitSummary = summary?.ai_summary.fit_summary
    const growthAdvice = summary?.ai_summary.growth_advice || []
    const roundCoverage = summary?.cross_round_profile.round_coverage || []
    const gapManifestations = (aiPrimaryGap?.manifestations || []).filter(Boolean)
    const gapImpactedRounds = (aiPrimaryGap?.impacted_rounds || []).filter(Boolean)

    if (loading) {
        return (
            <div className="flex min-h-screen bg-[#FAF9F6] dark:bg-[#101217]">
                <PersistentSidebar />
                <main className="flex-1 p-8">
                    <section className="rounded-2xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-10 text-center shadow-sm">
                        <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-[#111111] border-t-transparent" />
                        <p className="text-sm text-[#666666] dark:text-[#bcc5d3]">正在生成 AI 综合总结，请稍候...</p>
                    </section>
                </main>
            </div>
        )
    }

    return (
        <div className="flex min-h-screen bg-[#FAF9F6] dark:bg-[#101217]">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-7xl px-6 py-8">
                    <section className="rounded-3xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] p-8 shadow-sm">
                        <p className="text-xs font-medium uppercase tracking-[0.18em] text-[#999999] dark:text-[#8e98aa]">最近总览</p>
                        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#111111] dark:text-[#f4f7fb] sm:text-4xl">最近面试综合画像</h1>
                        <p className="mt-3 max-w-3xl text-sm leading-7 text-[#666666] dark:text-[#bcc5d3]">
                            上半部分看最近表现的变化，下半部分看跨轮次的综合能力、岗位贴合度和下一阶段最值得优先修正的问题。
                        </p>
                    </section>

                    <section className="mt-6 rounded-3xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-6 shadow-sm">
                        <div className="flex flex-wrap items-start justify-between gap-4">
                            <div>
                                <p className="text-xs font-medium uppercase tracking-[0.18em] text-[#999999] dark:text-[#8e98aa]">训练闭环</p>
                                <h2 className="mt-1 text-2xl font-semibold text-[#111111] dark:text-[#f4f7fb]">本周训练计划</h2>
                                <p className="mt-2 text-sm leading-7 text-[#666666] dark:text-[#bcc5d3]">
                                    按 计划-训练-验收-复训 的四段式推进，每个任务可直接跳转训练或发起 3 题验收短测。
                                </p>
                            </div>
                            {weeklyPlan ? (
                                <div className="rounded-2xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] px-4 py-3 text-sm text-[#555555] dark:text-[#bcc5d3]">
                                    <p>周期：{weeklyPlan.week_start_date} ~ {weeklyPlan.week_end_date}</p>
                                    <p className="mt-1">目标岗位：{weeklyPlan.plan.target_position_label}</p>
                                </div>
                            ) : null}
                        </div>

                        {weeklyPlanError ? (
                            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                {weeklyPlanError}
                            </div>
                        ) : null}

                        {weeklyPlanLoading ? (
                            <div className="mt-5 rounded-2xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] p-5 text-sm text-[#666666] dark:text-[#bcc5d3]">
                                正在生成本周训练计划...
                            </div>
                        ) : weeklyPlan ? (
                            <>
                                <div className="mt-5 grid gap-3 md:grid-cols-5">
                                    <div className="rounded-xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] px-3 py-2 text-sm text-[#555555] dark:text-[#bcc5d3]">计划中：{weeklyPlan.stage_summary.planned}</div>
                                    <div className="rounded-xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] px-3 py-2 text-sm text-[#555555] dark:text-[#bcc5d3]">训练中：{weeklyPlan.stage_summary.training}</div>
                                    <div className="rounded-xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] px-3 py-2 text-sm text-[#555555] dark:text-[#bcc5d3]">待验收：{weeklyPlan.stage_summary.validation}</div>
                                    <div className="rounded-xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] px-3 py-2 text-sm text-[#555555] dark:text-[#bcc5d3]">待回流：{weeklyPlan.stage_summary.reflow}</div>
                                    <div className="rounded-xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] px-3 py-2 text-sm text-[#555555] dark:text-[#bcc5d3]">已达标：{weeklyPlan.stage_summary.completed}</div>
                                </div>

                                <div className="mt-5 space-y-3">
                                    {weeklyPlan.tasks.length > 0 ? weeklyPlan.tasks.map((task) => {
                                        const taskBusy = actingTaskId === task.task_id
                                        return (
                                            <div key={task.task_id} className="rounded-2xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] p-4">
                                                <div className="flex flex-wrap items-center justify-between gap-3">
                                                    <div>
                                                        <div className="flex flex-wrap items-center gap-2">
                                                            <h3 className="text-base font-semibold text-[#111111] dark:text-[#f4f7fb]">{task.title}</h3>
                                                            <span className={`rounded-full px-2.5 py-1 text-xs ${statusClassName(task.status)}`}>{task.status_label}</span>
                                                        </div>
                                                        <p className="mt-1 text-sm text-[#666666] dark:text-[#bcc5d3]">
                                                            {task.round_label} · {task.position_label} · 目标分 {formatNumber(task.goal_score, 0)}
                                                            {Number.isFinite(Number(task.last_score)) ? ` · 最近得分 ${formatScore(task.last_score)}` : ''}
                                                        </p>
                                                        {task.focus_label ? (
                                                            <p className="mt-1 text-xs text-[#888888] dark:text-[#aab4c4]">聚焦：{task.focus_label}</p>
                                                        ) : null}
                                                    </div>

                                                    <div className="flex flex-wrap gap-2">
                                                        {shouldShowStartTraining(task.status) ? (
                                                            <button
                                                                onClick={() => void handleStartTraining(task.task_id)}
                                                                disabled={taskBusy}
                                                                className="rounded-lg border border-[#111111] bg-[#111111] px-3 py-2 text-sm text-white transition hover:bg-[#222222] disabled:cursor-not-allowed disabled:opacity-60"
                                                            >
                                                                {taskBusy ? '处理中...' : '一键训练'}
                                                            </button>
                                                        ) : null}
                                                        {shouldShowStartValidation(task.status) ? (
                                                            <button
                                                                onClick={() => void handleStartValidation(task.task_id)}
                                                                disabled={taskBusy}
                                                                className="rounded-lg border border-[#D9D4C8] bg-white px-3 py-2 text-sm text-[#333333] transition hover:border-[#111111] disabled:cursor-not-allowed disabled:opacity-60"
                                                            >
                                                                {taskBusy ? '处理中...' : '一键验收'}
                                                            </button>
                                                        ) : null}
                                                        {shouldShowMarkResult(task.status) ? (
                                                            <>
                                                                <button
                                                                    onClick={() => void handleMarkResult(task.task_id, true)}
                                                                    disabled={taskBusy}
                                                                    className="rounded-lg border border-[#2F6B45] bg-[#2F6B45] px-3 py-2 text-sm text-white transition hover:bg-[#245538] disabled:cursor-not-allowed disabled:opacity-60"
                                                                >
                                                                    {taskBusy ? '处理中...' : '标记达标'}
                                                                </button>
                                                                <button
                                                                    onClick={() => void handleMarkResult(task.task_id, false)}
                                                                    disabled={taskBusy || reflowBusy}
                                                                    className="rounded-lg border border-[#9D3A2E] bg-[#9D3A2E] px-3 py-2 text-sm text-white transition hover:bg-[#7f2f25] disabled:cursor-not-allowed disabled:opacity-60"
                                                                >
                                                                    {taskBusy || reflowBusy ? '处理中...' : '未达标并回流'}
                                                                </button>
                                                            </>
                                                        ) : null}
                                                    </div>
                                                </div>
                                            </div>
                                        )
                                    }) : (
                                        <div className="rounded-2xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] dark:bg-[#101217] p-4 text-sm text-[#666666] dark:text-[#bcc5d3]">
                                            本周暂无训练任务。
                                        </div>
                                    )}
                                </div>

                                <div className="mt-4 flex justify-end">
                                    <button
                                        onClick={() => void handleReflowPending()}
                                        disabled={reflowBusy || weeklyPlan.stage_summary.reflow <= 0}
                                        className="rounded-lg border border-[#D9D4C8] bg-white px-3 py-2 text-sm text-[#333333] transition hover:border-[#111111] disabled:cursor-not-allowed disabled:opacity-60"
                                    >
                                        {reflowBusy ? '回流中...' : '将未达标任务回流到下周'}
                                    </button>
                                </div>
                            </>
                        ) : (
                            <div className="mt-5 rounded-2xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] dark:bg-[#101217] p-4 text-sm text-[#666666] dark:text-[#bcc5d3]">
                                暂无可用的训练计划数据。
                            </div>
                        )}
                    </section>

                    {error ? (
                        <section className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-6 shadow-sm">
                            <div className="flex items-center gap-3 text-red-700">
                                <AlertCircle className="h-5 w-5" />
                                <p className="text-sm font-semibold">{error}</p>
                            </div>
                        </section>
                    ) : !summary ? null : (
                        <>
                            <section className="mt-6 grid gap-4 lg:grid-cols-4">
                                <MetricCard
                                    title="最近平均分"
                                    value={formatScore(summary.recent_metrics.averages.score)}
                                    hint={
                                        summary.recent_metrics.delta_from_previous == null
                                            ? '至少两场后显示环比变化'
                                            : `最近一场较前一场 ${summary.recent_metrics.delta_from_previous >= 0 ? '+' : ''}${formatNumber(summary.recent_metrics.delta_from_previous)}`
                                    }
                                    icon={<TrendingUp className="h-4 w-4" />}
                                />
                                <MetricCard
                                    title="平均稳定度"
                                    value={formatScore(summary.recent_metrics.averages.stability)}
                                    hint="来自轮次稳定性与校准口径"
                                    icon={<Gauge className="h-4 w-4" />}
                                />
                                <MetricCard
                                    title="风险热度"
                                    value={formatRiskLabel(summary.recent_metrics.averages.risk)}
                                    hint={
                                        Number.isFinite(Number(summary.recent_metrics.averages.risk))
                                            ? `均值 ${formatNumber(summary.recent_metrics.averages.risk)}%`
                                            : '暂无风险热度数据'
                                    }
                                    icon={<ShieldCheck className="h-4 w-4" />}
                                />
                                <MetricCard
                                    title="四轮覆盖"
                                    value={`${summary.cross_round_profile.covered_round_count}/4`}
                                    hint={`${summary.cross_round_profile.sample_count} 场样本组成近期综合画像`}
                                    icon={<Target className="h-4 w-4" />}
                                />
                            </section>

                            <section className="mt-6 grid gap-6 xl:grid-cols-[1.4fr_1fr]">
                                <ChartCard title="综合得分趋势" description="时间序列适合看最近 5 场的主分变化，判断当前训练是否真的在向上。">
                                    <div className="h-[320px] w-full">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={trendData} margin={{ top: 12, right: 16, left: 0, bottom: 0 }}>
                                                <CartesianGrid stroke="#ECE7DD" strokeOpacity={0.5} />
                                                <XAxis dataKey="label" tick={{ fill: '#8C867C', fontSize: 12 }} axisLine={false} tickLine={false} />
                                                <YAxis domain={[0, 100]} tick={{ fill: '#8C867C', fontSize: 12 }} axisLine={false} tickLine={false} width={34} />
                                                <Tooltip
                                                    contentStyle={{
                                                        borderRadius: 16,
                                                        border: '1px solid #E5E5E5',
                                                        backgroundColor: '#FFFFFF',
                                                        color: '#111111'
                                                    }}
                                                    formatter={(value: unknown) => [`${formatNumber(Number(value))}`, '综合得分']}
                                                />
                                                <Line type="monotone" dataKey="score" stroke="#4C6A8A" strokeWidth={2.5} dot={{ r: 4, fill: '#4C6A8A' }} activeDot={{ r: 5 }} connectNulls />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                </ChartCard>

                                <ChartCard title="面试类型分布" description="这张图看最近 7 天训练重心是否过于单一，只统计已明确记录轮次的面试。">
                                    <div className="h-[320px] w-full">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <PieChart>
                                                <Pie
                                                    data={summary.weekly_distribution}
                                                    dataKey="value"
                                                    nameKey="name"
                                                    cx="50%"
                                                    cy="50%"
                                                    innerRadius={58}
                                                    outerRadius={92}
                                                    paddingAngle={3}
                                                >
                                                    {summary.weekly_distribution.map((entry, index) => (
                                                        <Cell key={`${entry.name}-${index}`} fill={ROUND_COLORS[index % ROUND_COLORS.length]} />
                                                    ))}
                                                </Pie>
                                                <Tooltip
                                                    contentStyle={{ borderRadius: 16, border: '1px solid #E5E5E5', backgroundColor: '#FFFFFF' }}
                                                    formatter={(value: unknown) => [`${value} 场`, '次数']}
                                                />
                                                <Legend verticalAlign="bottom" iconType="circle" wrapperStyle={{ paddingTop: 20 }} />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    </div>
                                </ChartCard>
                            </section>

                            <section className="mt-6 grid gap-6 xl:grid-cols-[1fr_1.2fr]">
                                <ChartCard title="核心能力轴均值" description="横向对比更适合看内容、表达、镜头三类能力的相对高低，而不是只看一个总分。">
                                    <div className="h-[300px] w-full">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart data={axisData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                                                <CartesianGrid stroke="#ECE7DD" vertical={false} />
                                                <XAxis dataKey="name" tick={{ fill: '#8C867C', fontSize: 12 }} axisLine={false} tickLine={false} />
                                                <YAxis domain={[0, 100]} tick={{ fill: '#8C867C', fontSize: 12 }} axisLine={false} tickLine={false} width={34} />
                                                <Tooltip
                                                    contentStyle={{ borderRadius: 16, border: '1px solid #E5E5E5', backgroundColor: '#FFFFFF' }}
                                                    formatter={(value: unknown) => [`${formatNumber(Number(value))}`, '均值']}
                                                />
                                                <Bar dataKey="score" radius={[10, 10, 0, 0]}>
                                                    {axisData.map((item) => (
                                                        <Cell key={item.name} fill={item.fill} />
                                                    ))}
                                                </Bar>
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                </ChartCard>

                                <ChartCard title="稳定性与风险走势" description="这两项都属于过程质量信号，放在同一时间轴上更容易看出是否越来越稳。">
                                    <div className="h-[300px] w-full">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={trendData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                                                <CartesianGrid stroke="#ECE7DD" vertical={false} />
                                                <XAxis dataKey="label" tick={{ fill: '#8C867C', fontSize: 12 }} axisLine={false} tickLine={false} />
                                                <YAxis domain={[0, 100]} tick={{ fill: '#8C867C', fontSize: 12 }} axisLine={false} tickLine={false} width={34} />
                                                <Tooltip
                                                    contentStyle={{ borderRadius: 16, border: '1px solid #E5E5E5', backgroundColor: '#FFFFFF' }}
                                                    formatter={(value: unknown, name: string) => [`${formatNumber(Number(value))}${name === '风险热度' ? '%' : ''}`, name]}
                                                />
                                                <Legend />
                                                <Line type="monotone" dataKey="stability" name="稳定度" stroke="#4C6A8A" strokeWidth={2.4} dot={{ r: 4, fill: '#4C6A8A' }} connectNulls />
                                                <Line type="monotone" dataKey="risk" name="风险热度" stroke="#B67A2D" strokeWidth={2.2} dot={{ r: 4, fill: '#B67A2D' }} connectNulls />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                </ChartCard>
                            </section>

                            <section className="mt-6 grid gap-6 xl:grid-cols-[1.2fr_1fr]">
                                <section className="rounded-3xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-6 shadow-sm">
                                    <div className="flex items-center gap-2">
                                        <BarChart3 className="h-5 w-5 text-[#556987] dark:text-[#bcc5d3]" />
                                        <h2 className="text-xl font-semibold text-[#111111] dark:text-[#f4f7fb]">四轮综合能力画像</h2>
                                    </div>
                                    <p className="mt-2 text-sm leading-6 text-[#666666] dark:text-[#bcc5d3]">
                                        这个画像不是单场报告，而是把最近 30 天内四类轮次的有效样本合并后，得到你这一阶段更稳定的能力轮廓。
                                    </p>

                                    <div className="mt-4 flex flex-wrap gap-2">
                                        <span className="rounded-full bg-[#F3EFE4] px-3 py-1 text-xs text-[#6A5A2B]">
                                            目标岗位：{summary.cross_round_profile.target_position_label || '当前目标岗位'}
                                        </span>
                                        {roundCoverage.map((item) => (
                                            <span
                                                key={item.round_type}
                                                className={`rounded-full px-3 py-1 text-xs ${item.status === 'ready'
                                                    ? 'bg-[#EAF5ED] text-[#2F6B45]'
                                                    : 'bg-[#F2F2F0] text-[#666666] dark:text-[#bcc5d3]'
                                                    }`}
                                            >
                                                {item.label} {item.count > 0 ? `${item.count} 场` : '样本不足'}
                                            </span>
                                        ))}
                                    </div>

                                    <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_0.95fr]">
                                        <div className="rounded-2xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] p-5">
                                            <p className="text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">综合画像结论</p>
                                            <p className="mt-3 text-sm leading-7 text-[#555555] dark:text-[#bcc5d3]">
                                                {summary.ai_summary.profile_summary || '近期样本还不足以形成稳定的综合画像结论。'}
                                            </p>

                                            <div className="mt-5 space-y-3">
                                                {radarDimensions.map((item) => (
                                                    <div key={item.key} className="rounded-xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-3">
                                                        <div className="flex items-center justify-between gap-3">
                                                            <span className="text-sm text-[#111111] dark:text-[#f4f7fb]">{item.label}</span>
                                                            <span className="text-sm font-semibold text-[#111111] dark:text-[#f4f7fb]">{formatScore(item.score)}</span>
                                                        </div>
                                                        <div className="mt-2 h-2 overflow-hidden rounded-full bg-[#ECE7DD] dark:bg-[#2d3542]">
                                                            <div className="h-full rounded-full bg-[#4C6A8A]" style={{ width: `${Math.max(0, Math.min(100, item.score))}%` }} />
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                </section>

                                <section className="rounded-3xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-6 shadow-sm">
                                    <div className="flex items-center gap-2">
                                        <Briefcase className="h-5 w-5 text-[#556987] dark:text-[#bcc5d3]" />
                                        <h2 className="text-xl font-semibold text-[#111111] dark:text-[#f4f7fb]">岗位匹配度</h2>
                                    </div>
                                    <p className="mt-2 text-sm leading-6 text-[#666666] dark:text-[#bcc5d3]">
                                        这个分数按最近四轮综合样本计算，反映的是“你现在像不像这个岗位的候选人”，而不只是答对了多少题。
                                    </p>

                                    <div className="mt-5 h-[210px]">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <PieChart>
                                                <Pie
                                                    data={[
                                                        { name: '匹配度', value: Math.max(0, Math.min(100, summary.cross_round_profile.fit_score || 0)) },
                                                        { name: '剩余', value: Math.max(0, 100 - Math.max(0, Math.min(100, summary.cross_round_profile.fit_score || 0))) },
                                                    ]}
                                                    dataKey="value"
                                                    startAngle={180}
                                                    endAngle={0}
                                                    innerRadius={70}
                                                    outerRadius={98}
                                                    stroke="none"
                                                >
                                                    {FIT_GAUGE_COLORS.map((color, index) => (
                                                        <Cell key={`fit-gauge-${index}`} fill={color} />
                                                    ))}
                                                </Pie>
                                                <Tooltip formatter={(value: unknown) => [`${formatNumber(Number(value))}`, '匹配度']} />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    </div>

                                    <div className="-mt-20 text-center">
                                        <p className="text-4xl font-semibold text-[#111111] dark:text-[#f4f7fb]">{formatScore(summary.cross_round_profile.fit_score)}</p>
                                        <p className="mt-2 text-sm text-[#666666] dark:text-[#bcc5d3]">{summary.cross_round_profile.target_position_label || '当前目标岗位'}</p>
                                    </div>

                                    <div className="mt-6 grid gap-3">
                                        {fitBreakdown.map((item) => (
                                            <div key={item.key} className="rounded-xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] p-3">
                                                <div className="flex items-center justify-between gap-2">
                                                    <span className="text-sm text-[#111111] dark:text-[#f4f7fb]">{item.label}</span>
                                                    <span className="text-sm font-semibold text-[#111111] dark:text-[#f4f7fb]">{formatScore(item.score)}</span>
                                                </div>
                                                <div className="mt-2 h-2 overflow-hidden rounded-full bg-[#ECE7DD]">
                                                    <div className="h-full rounded-full bg-[#111111]" style={{ width: `${Math.max(0, Math.min(100, Number(item.score || 0)))}%` }} />
                                                </div>
                                            </div>
                                        ))}
                                    </div>

                                    <div className="mt-5 rounded-2xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FCFBF8] dark:bg-[#181c24] p-4">
                                        <p className="text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">{fitSummary?.summary || '岗位匹配结论生成中'}</p>
                                        <p className="mt-2 text-sm leading-7 text-[#666666] dark:text-[#bcc5d3]">{fitSummary?.blocker || '当前尚未识别出明确的限制项。'}</p>
                                    </div>
                                </section>
                            </section>

                            <section className="mt-6 space-y-6">
                                <section className="rounded-3xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-6 shadow-sm">
                                    <div className="flex items-center gap-2">
                                        <Target className="h-5 w-5 text-[#556987] dark:text-[#bcc5d3]" />
                                        <h2 className="text-xl font-semibold text-[#111111] dark:text-[#f4f7fb]">最大短板</h2>
                                    </div>
                                    <p className="mt-2 text-sm leading-6 text-[#666666] dark:text-[#bcc5d3]">
                                        近期四轮样本中重复出现、并且持续拖累岗位匹配判断的主短板。
                                    </p>

                                    <div className="mt-5 rounded-2xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] p-5">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className="rounded-full bg-[#FCEBE9] px-3 py-1 text-xs text-[#9D3A2E]">综合诊断</span>
                                            <h3 className="text-lg font-semibold text-[#111111] dark:text-[#f4f7fb]">{aiPrimaryGap?.title || '综合短板待补充'}</h3>
                                        </div>
                                        <div className="mt-4 rounded-2xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-5">
                                            <p className="text-[15px] leading-8 text-[#555555] dark:text-[#bcc5d3]">
                                                {aiPrimaryGap?.description || aiPrimaryGap?.summary || aiPrimaryGap?.reason || '近期有效样本仍偏少，暂时还没有稳定重复出现的主短板结论。'}
                                            </p>
                                        </div>

                                        {(gapImpactedRounds.length > 0 || gapManifestations.length > 0) ? (
                                            <div className="mt-4 grid gap-3 md:grid-cols-2">
                                                <div className="rounded-2xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-4">
                                                    <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#999999] dark:text-[#8e98aa]">主要体现</p>
                                                    {gapImpactedRounds.length > 0 ? (
                                                        <p className="mt-3 text-sm leading-7 text-[#555555] dark:text-[#bcc5d3]">
                                                            这个问题当前最明显地出现在
                                                            {gapImpactedRounds.map((item, index) => (
                                                                <span key={item} className="font-medium text-[#111111] dark:text-[#f4f7fb]">
                                                                    {`${index === 0 ? '' : '、'}${item}`}
                                                                </span>
                                                            ))}
                                                            ，说明它不是某一场的偶发现象，而是跨轮次重复出现的短板。
                                                        </p>
                                                    ) : (
                                                        <p className="mt-3 text-sm leading-7 text-[#555555] dark:text-[#bcc5d3]">
                                                            这个问题已经开始跨场次重复出现，建议尽早把它从“偶发问题”变成“可控问题”。
                                                        </p>
                                                    )}
                                                    {gapManifestations.length > 0 ? (
                                                        <div className="mt-4 space-y-2">
                                                            {gapManifestations.slice(0, 2).map((item, index) => (
                                                                <div key={`${item}-${index}`} className="rounded-xl border border-[#EFEAE1] bg-[#FCFBF8] dark:bg-[#181c24] px-4 py-3 text-sm leading-7 text-[#555555] dark:text-[#bcc5d3]">
                                                                    {item}
                                                                </div>
                                                            ))}
                                                        </div>
                                                    ) : null}
                                                </div>

                                                <div className="rounded-2xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-4">
                                                    <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#999999] dark:text-[#8e98aa]">重复出现信号</p>
                                                    <p className="mt-3 text-sm leading-7 text-[#555555] dark:text-[#bcc5d3]">
                                                        {gapManifestations.length > 0 ? gapManifestations.slice(0, 3).join('；') : '暂无稳定重复信号，建议继续积累有效样本。'}
                                                    </p>
                                                </div>
                                            </div>
                                        ) : null}

                                    </div>
                                </section>

                                <section className="rounded-3xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-6 shadow-sm">
                                    <div className="flex items-center gap-2">
                                        <Sparkles className="h-5 w-5 text-[#556987] dark:text-[#bcc5d3]" />
                                        <h2 className="text-xl font-semibold text-[#111111] dark:text-[#f4f7fb]">成长建议</h2>
                                    </div>
                                    <p className="mt-2 text-sm leading-6 text-[#666666] dark:text-[#bcc5d3]">
                                        这些建议来自近期四轮综合面试，揭示下一阶段最值得投入时间的动作。
                                    </p>

                                    <div className="mt-5">
                                        {growthAdvice.length > 0 ? (
                                            <div className="grid gap-3 md:grid-cols-3">
                                                {growthAdvice.map((item, index) => (
                                                    <div key={`${item.title}-${index}`} className="rounded-2xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] p-4">
                                                        <p className="text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">{item.title || `建议 ${index + 1}`}</p>
                                                        <p className="mt-2 text-sm leading-7 text-[#555555] dark:text-[#bcc5d3]">{item.advice || '暂时没有可执行建议。'}</p>
                                                    </div>
                                                ))}
                                            </div>
                                        ) : (
                                            <div className="rounded-2xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] dark:bg-[#101217] p-4 text-sm text-[#666666] dark:text-[#bcc5d3]">
                                                当前还没有足够的聚合证据来生成成长建议。
                                            </div>
                                        )}
                                    </div>
                                </section>
                            </section>

                            {recommendedReview ? (
                                <section className="mt-6 rounded-3xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-6 shadow-sm">
                                    <div className="flex flex-wrap items-center justify-between gap-4">
                                        <div className="max-w-3xl">
                                            <p className="text-sm font-medium text-[#999999] dark:text-[#8e98aa]">建议优先复盘</p>
                                            <div className="mt-2 flex flex-wrap items-center gap-3">
                                                <h2 className="text-2xl font-semibold text-[#111111] dark:text-[#f4f7fb]">{recommendedReview.round_label}</h2>
                                                <span className="rounded-full bg-[#F3EFE4] px-3 py-1 text-xs text-[#6A5A2B]">
                                                    {formatDate(recommendedReview.created_at)}
                                                </span>
                                                <span className="rounded-full border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] px-3 py-1 text-xs text-[#555555] dark:text-[#bcc5d3]">
                                                    综合得分 {formatScore(recommendedReview.score)}
                                                </span>
                                            </div>
                                            <p className="mt-3 text-sm leading-7 text-[#666666] dark:text-[#bcc5d3]">{recommendedReview.reason}</p>
                                        </div>

                                        <Link
                                            href={recommendedReview.report_url}
                                            className="inline-flex items-center gap-2 rounded-xl bg-[#111111] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#222222]"
                                        >
                                            打开这场报告
                                            <ArrowRight className="h-4 w-4" />
                                        </Link>
                                    </div>
                                </section>
                            ) : null}

                        </>
                    )}
                </div>
            </main>
        </div>
    )
}

function MetricCard({
    title,
    value,
    hint,
    icon,
}: {
    title: string
    value: string
    hint: string
    icon: React.ReactNode
}) {
    return (
        <div className="rounded-2xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-5 shadow-sm">
            <div className="flex items-center gap-2 text-sm text-[#666666] dark:text-[#bcc5d3]">
                {icon}
                <span>{title}</span>
            </div>
            <p className="mt-4 text-3xl font-semibold text-[#111111] dark:text-[#f4f7fb]">{value}</p>
            <p className="mt-2 text-sm leading-6 text-[#777777] dark:text-[#bcc5d3]">{hint}</p>
        </div>
    )
}

function ChartCard({
    title,
    description,
    children,
}: {
    title: string
    description: string
    children: React.ReactNode
}) {
    return (
        <section className="rounded-3xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-6 shadow-sm">
            <h2 className="text-xl font-semibold text-[#111111] dark:text-[#f4f7fb]">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-[#666666] dark:text-[#bcc5d3]">{description}</p>
            <div className="mt-5">{children}</div>
        </section>
    )
}

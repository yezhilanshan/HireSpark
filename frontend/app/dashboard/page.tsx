'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowRight, BellRing, Clock3, Play, Target, TrendingUp } from 'lucide-react'
import { motion, type Variants } from 'motion/react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { getBackendBaseUrl } from '@/lib/backend'

const BACKEND_API_BASE = getBackendBaseUrl()

type GrowthDimension = {
    key: string
    label: string
    score: number
}

type GrowthReport = {
    summary?: {
        overall_score?: number
    }
    dimensions?: GrowthDimension[]
    score_breakdown?: Record<string, number>
    coaching?: {
        next_actions?: string[]
        weaknesses?: string[]
    }
    weaknesses?: string[]
    improvement_plan?: Array<{ action?: string; focus?: string }>
}

type GrowthApiResult = {
    success: boolean
    report?: GrowthReport | null
    latest_report?: GrowthReport | null
    history?: {
        session_count?: number
        average_score?: number
    }
}

type InterviewApiResult = {
    success: boolean
    interviews?: InterviewRecord[]
}

type ResumeApiResult = {
    success: boolean
    resume?: {
        parsed_data?: {
            basic_info?: {
                name?: string
                target_role?: string
            }
            raw_text?: string
        }
    }
}

type InterviewRecord = {
    id?: number
    interview_id?: string
    created_at?: string
    start_time?: string
    round_type?: string
    dominant_round?: string
    duration?: number
    risk_level?: string
    events_count?: number
    overall_score?: number | null
    score_source?: string
    scored_turns?: number
}

type RecentSession = {
    key: string
    title: string
    meta: string
    score: number | null
}

type DashboardState = {
    loading: boolean
    dataWarning: string
    totalSessions: number
    weekPracticeCount: number
    averageScore: number
    latestScore: number
    weakestLabel: string
    candidateName: string
    targetRole: string
    practiceHours: number
    weeklyScoreDelta: number
    recentSessions: RecentSession[]
}

type DashboardCachePayload = {
    cachedAt: number
    state: DashboardState
}

const INITIAL_STATE: DashboardState = {
    loading: true,
    dataWarning: '',
    totalSessions: 0,
    weekPracticeCount: 0,
    averageScore: 0,
    latestScore: 0,
    weakestLabel: '项目细节深挖',
    candidateName: '候选人',
    targetRole: 'Java 后端工程师',
    practiceHours: 0,
    weeklyScoreDelta: 0,
    recentSessions: [],
}

const DASHBOARD_CACHE_KEY = 'hirespark.dashboard.cache.v1'
const DASHBOARD_CACHE_TTL_MS = 1000 * 60 * 10

let dashboardMemoryCache: DashboardCachePayload | null = null

function toFiniteNumber(value: unknown, fallback = 0): number {
    const numeric = Number(value)
    return Number.isFinite(numeric) ? numeric : fallback
}

function normalizeCachedDashboardState(raw: unknown): DashboardState | null {
    if (!raw || typeof raw !== 'object') return null

    const candidate = raw as Partial<DashboardState>
    const recentSessions = Array.isArray(candidate.recentSessions)
        ? candidate.recentSessions
            .map((item, index) => {
                if (!item || typeof item !== 'object') return null
                const session = item as Partial<RecentSession>
                const scoreRaw = session.score
                const score = scoreRaw === null ? null : toFiniteNumber(scoreRaw, 0)
                return {
                    key: String(session.key || index),
                    title: String(session.title || '未命名会话'),
                    meta: String(session.meta || ''),
                    score,
                }
            })
            .filter((item): item is RecentSession => item !== null)
        : []

    return {
        loading: false,
        dataWarning: String(candidate.dataWarning || ''),
        totalSessions: Math.max(0, toFiniteNumber(candidate.totalSessions, 0)),
        weekPracticeCount: Math.max(0, toFiniteNumber(candidate.weekPracticeCount, 0)),
        averageScore: toFiniteNumber(candidate.averageScore, 0),
        latestScore: toFiniteNumber(candidate.latestScore, 0),
        weakestLabel: String(candidate.weakestLabel || INITIAL_STATE.weakestLabel),
        candidateName: String(candidate.candidateName || INITIAL_STATE.candidateName),
        targetRole: String(candidate.targetRole || INITIAL_STATE.targetRole),
        practiceHours: Math.max(0, toFiniteNumber(candidate.practiceHours, 0)),
        weeklyScoreDelta: toFiniteNumber(candidate.weeklyScoreDelta, 0),
        recentSessions,
    }
}

function readDashboardCache(): DashboardState | null {
    const now = Date.now()

    if (dashboardMemoryCache && now - dashboardMemoryCache.cachedAt <= DASHBOARD_CACHE_TTL_MS) {
        return { ...dashboardMemoryCache.state, loading: false }
    }

    try {
        const raw = window.sessionStorage.getItem(DASHBOARD_CACHE_KEY)
        if (!raw) return null

        const parsed = JSON.parse(raw) as Partial<DashboardCachePayload>
        const cachedAt = toFiniteNumber(parsed.cachedAt, 0)
        if (!cachedAt || now - cachedAt > DASHBOARD_CACHE_TTL_MS) {
            window.sessionStorage.removeItem(DASHBOARD_CACHE_KEY)
            return null
        }

        const normalized = normalizeCachedDashboardState(parsed.state)
        if (!normalized) {
            window.sessionStorage.removeItem(DASHBOARD_CACHE_KEY)
            return null
        }

        dashboardMemoryCache = {
            cachedAt,
            state: normalized,
        }
        return { ...normalized, loading: false }
    } catch {
        return null
    }
}

function writeDashboardCache(state: DashboardState): void {
    const cacheState: DashboardState = { ...state, loading: false }
    const payload: DashboardCachePayload = {
        cachedAt: Date.now(),
        state: cacheState,
    }

    dashboardMemoryCache = payload
    try {
        window.sessionStorage.setItem(DASHBOARD_CACHE_KEY, JSON.stringify(payload))
    } catch {
        // ignore storage failures
    }
}

async function parseApiPayload<T extends { success: boolean }>(response: Response): Promise<T | null> {
    if (!response.ok) return null

    const contentType = response.headers.get('content-type') || ''
    if (!contentType.toLowerCase().includes('application/json')) return null

    try {
        const payload: unknown = await response.json()
        if (!payload || typeof payload !== 'object') return null
        if ((payload as { success?: unknown }).success !== true) return null
        return payload as T
    } catch {
        return null
    }
}

function greetingText() {
    const hour = new Date().getHours()
    if (hour < 6) return '凌晨好'
    if (hour < 12) return '早上好'
    if (hour < 18) return '下午好'
    return '晚上好'
}

function getWeekStart(date: Date): Date {
    const start = new Date(date)
    start.setHours(0, 0, 0, 0)
    const day = (start.getDay() + 6) % 7
    start.setDate(start.getDate() - day)
    return start
}

function toTimestamp(value?: string): number {
    if (!value) return 0
    const time = new Date(value).getTime()
    return Number.isNaN(time) ? 0 : time
}

function deriveScore(record: InterviewRecord): number {
    const raw = Number(record.overall_score)
    if (!Number.isFinite(raw)) return 0
    return Math.max(0, Math.min(100, Number(raw.toFixed(1))))
}

function getStructuredScore(record: InterviewRecord): number | null {
    if (record.score_source !== 'structured_evaluation') return null
    const score = deriveScore(record)
    return score > 0 ? score : null
}

function extractNameFromRawText(rawText?: string): string {
    const source = typeof rawText === 'string' ? rawText : ''
    if (!source.trim()) return ''

    const matched = (
        source.match(/(?:姓名|名字)\s*[:：]\s*([^\n\r,，]+)/)?.[1]?.trim()
        || source.match(/(?:候选人|Candidate)\s*[:：]\s*([^\n\r,，]+)/)?.[1]?.trim()
        || ''
    )

    const cleaned = matched
        .split(/[;；|]/)[0]
        .replace(/\s*(性别|电话|手机号|邮箱|Email|所在城市|城市)\s*[:：]?.*$/i, '')
        .trim()

    if (!cleaned || cleaned.length > 20) return ''
    return cleaned
}

function roundLabel(roundType?: string): string {
    const normalized = String(roundType || '').trim().toLowerCase()
    if (normalized === 'technical') return '技术基础面'
    if (normalized === 'project') return '项目深度面'
    if (normalized === 'system_design') return '系统设计面'
    if (normalized === 'hr') return 'HR 综合面'
    return String(roundType || '').trim()
}

function formatSessionMeta(record: InterviewRecord): string {
    const timeValue = toTimestamp(record.created_at || record.start_time)
    const time = timeValue ? new Date(timeValue) : null

    const timeLabel = time
        ? `${time.getMonth() + 1}月${time.getDate()}日 ${String(time.getHours()).padStart(2, '0')}:${String(time.getMinutes()).padStart(2, '0')}`
        : '时间未记录'

    const duration = Math.max(0, Number(record.duration || 0))
    if (duration <= 0) {
        return `进行时间 ${timeLabel}`
    }

    const minutes = Math.round(duration / 60)
    if (minutes <= 0) {
        return `进行时间 ${timeLabel} · 时长 ${duration} 秒`
    }
    return `进行时间 ${timeLabel} · 时长 ${minutes} 分钟`
}

function buildSessionTitle(record: InterviewRecord): string {
    return roundLabel(record.dominant_round || record.round_type)
}

function average(values: number[]): number {
    if (!values.length) return 0
    return values.reduce((sum, value) => sum + value, 0) / values.length
}

function formatWeeklyDelta(delta: number): string {
    if (delta > 0) return `较上周提升 ${delta.toFixed(1)} 分`
    if (delta < 0) return `较上周下降 ${Math.abs(delta).toFixed(1)} 分`
    return '与上周基本持平'
}

function getAvatarInitial(name: string): string {
    const trimmed = name.trim()
    if (!trimmed) return 'A'
    const first = trimmed[0]
    const upper = first.toUpperCase()
    return /[A-Z]/.test(upper) ? upper : first
}

function reminderToneClasses(tone?: string): string {
    if (tone === 'success') return 'border-emerald-200 bg-emerald-50 text-emerald-800'
    if (tone === 'warning') return 'border-amber-200 bg-amber-50 text-amber-800'
    if (tone === 'danger') return 'border-red-200 bg-red-50 text-red-800'
    return 'border-sky-200 bg-sky-50 text-sky-800'
}

function normalizeDimensions(report: GrowthReport | null | undefined): GrowthDimension[] {
    if (!report) return []

    if (Array.isArray(report.dimensions) && report.dimensions.length > 0) {
        return report.dimensions.map((item) => ({
            key: item.key,
            label: item.label,
            score: Number(item.score || 0),
        }))
    }

    const fallbackLabels: Record<string, string> = {
        technical: '技术基础',
        project: '项目表达',
        logic: '逻辑条理',
        communication: '沟通表达',
        stress: '抗压表现',
    }

    return Object.entries(report.score_breakdown || {}).map(([key, score]) => ({
        key,
        label: fallbackLabels[key] || key,
        score: Number(score || 0),
    }))
}

const containerVariants: Variants = {
    hidden: { opacity: 0 },
    show: {
        opacity: 1,
        transition: { staggerChildren: 0.1 },
    },
}

const itemVariants: Variants = {
    hidden: { opacity: 0, y: 15 },
    show: {
        opacity: 1,
        y: 0,
        transition: { type: 'spring', stiffness: 300, damping: 30 },
    },
}

export default function HomePage() {
    const router = useRouter()
    const [state, setState] = useState<DashboardState>(() => {
        if (typeof window === 'undefined') return INITIAL_STATE
        return readDashboardCache() || INITIAL_STATE
    })
    const reminders: Array<{
        id: string
        tone?: string
        title: string
        message: string
        cta_label?: string
        cta_href?: string
    }> = []
    const reminderSummary: { current_streak_days?: number } = {}

    useEffect(() => {
        let cancelled = false
        const cachedState = readDashboardCache()

        if (cachedState) {
            setState(cachedState)
        }

        const load = async () => {
            const [growthResult, interviewsResult, resumeResult] = await Promise.allSettled([
                fetch(`${BACKEND_API_BASE}/api/growth-report/latest`, { cache: 'no-store' }),
                fetch(`${BACKEND_API_BASE}/api/interviews?limit=80`, { cache: 'no-store' }),
                fetch(`${BACKEND_API_BASE}/api/resume/latest`, { cache: 'no-store' }),
            ])

            let growth: GrowthApiResult | null = null
            let interviews: InterviewApiResult | null = null
            let resume: ResumeApiResult | null = null
            const warningModules: string[] = []

            if (growthResult.status === 'fulfilled') {
                growth = await parseApiPayload<GrowthApiResult>(growthResult.value)
            }

            if (interviewsResult.status === 'fulfilled') {
                interviews = await parseApiPayload<InterviewApiResult>(interviewsResult.value)
            }

            if (resumeResult.status === 'fulfilled') {
                resume = await parseApiPayload<ResumeApiResult>(resumeResult.value)
            }

            if (!growth) warningModules.push('成长报告')
            if (!interviews) warningModules.push('面试记录')
            if (!resume) warningModules.push('简历信息')

            const latestReport = growth?.latest_report || growth?.report || null
            const dimensions = normalizeDimensions(latestReport)
            const weakest = dimensions.length
                ? dimensions.reduce((acc, item) => (item.score < acc.score ? item : acc), dimensions[0]).label
                : '项目细节深挖'

            const interviewList = Array.isArray(interviews?.interviews) ? interviews.interviews : []
            const now = Date.now()

            const weekStart = getWeekStart(new Date())
            const previousWeekStart = new Date(weekStart)
            previousWeekStart.setDate(previousWeekStart.getDate() - 7)

            const weekPracticeCount = interviewList.filter((item) => {
                const time = toTimestamp(item.created_at || item.start_time)
                return time >= weekStart.getTime() && time <= now
            }).length

            const thisWeekScores = interviewList
                .filter((item) => {
                    const time = toTimestamp(item.created_at || item.start_time)
                    return time >= weekStart.getTime() && time <= now
                })
                .map((item) => getStructuredScore(item))
                .filter((item): item is number => item !== null)

            const previousWeekScores = interviewList
                .filter((item) => {
                    const time = toTimestamp(item.created_at || item.start_time)
                    return time >= previousWeekStart.getTime() && time < weekStart.getTime()
                })
                .map((item) => getStructuredScore(item))
                .filter((item): item is number => item !== null)

            const totalDuration = interviewList.reduce((sum, item) => {
                return sum + Math.max(0, Number(item.duration || 0))
            }, 0)

            const recentSessions = [...interviewList]
                .sort((a, b) => toTimestamp(b.created_at || b.start_time) - toTimestamp(a.created_at || a.start_time))
                .filter((item) => Boolean(String(item.dominant_round || item.round_type || '').trim()))
                .slice(0, 3)
                .map((item, index) => ({
                    key: item.interview_id || `${item.id || index}`,
                    title: buildSessionTitle(item),
                    meta: formatSessionMeta(item),
                    score: getStructuredScore(item),
                }))

            const parsed = resume?.resume?.parsed_data
            const candidateName = parsed?.basic_info?.name?.trim() || extractNameFromRawText(parsed?.raw_text) || '候选人'

            const weeklyScoreDelta = thisWeekScores.length && previousWeekScores.length
                ? average(thisWeekScores) - average(previousWeekScores)
                : 0

            if (cancelled) return

            const nextState: DashboardState = {
                loading: false,
                dataWarning: warningModules.length ? `以下数据暂未同步：${warningModules.join('、')}` : '',
                totalSessions: Math.max(Number(growth?.history?.session_count || 0), Number(interviewList.length || 0)),
                weekPracticeCount,
                averageScore: Number(growth?.history?.average_score || latestReport?.summary?.overall_score || 0),
                latestScore: Number(latestReport?.summary?.overall_score || 0),
                weakestLabel: weakest,
                candidateName,
                targetRole: parsed?.basic_info?.target_role || 'Java 后端工程师',
                practiceHours: Number((totalDuration / 3600).toFixed(1)),
                weeklyScoreDelta,
                recentSessions,
            }

            writeDashboardCache(nextState)
            setState(nextState)
        }

        load().catch(() => {
            if (!cancelled) {
                setState((prev) => ({
                    ...prev,
                    loading: false,
                    dataWarning: cachedState
                        ? (prev.dataWarning || '网络波动，已展示缓存数据。')
                        : '数据同步失败，请稍后重试。',
                }))
            }
        })

        return () => {
            cancelled = true
        }
    }, [])

    const greeting = useMemo(() => greetingText(), [])
    const avatarInitial = useMemo(() => getAvatarInitial(state.candidateName), [state.candidateName])

    return (
        <div className="flex-1 overflow-y-auto p-8 lg:p-12">
            <motion.div className="mx-auto max-w-5xl space-y-12" variants={containerVariants} initial="hidden" animate="show">
                <motion.header variants={itemVariants} className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <h1 className="text-3xl font-serif tracking-tight text-[#111111]">
                            {greeting}，{state.candidateName}。
                        </h1>
                        <p className="mt-2 text-[#666666]">今天继续打磨你的面试能力，向目标岗位再进一步。</p>
                    </div>

                    <div className="flex items-center gap-6">
                        <div className="hidden items-center gap-2 rounded-full border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] px-3 py-1.5 text-xs text-[#999999] dark:text-[#8e98aa] shadow-sm md:flex">
                            <span className="font-medium">快捷键</span>
                            <kbd className="rounded bg-[#F5F5F5] dark:bg-[#2d3542] px-1.5 py-0.5 text-[#111111] dark:text-[#f4f7fb]">Ctrl K</kbd>
                        </div>
                        <div className="flex items-center gap-4">
                            <div className="hidden text-right sm:block">
                                <p className="text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">{state.targetRole}</p>
                                <p className="text-xs text-[#999999] dark:text-[#8e98aa]">目标岗位</p>
                            </div>
                            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#EBE9E0] dark:bg-[#2d3542] font-medium text-[#111111] dark:text-[#f4f7fb]">
                                {avatarInitial}
                            </div>
                        </div>
                    </div>
                </motion.header>

                <motion.div variants={itemVariants}>
                    <Card className="flex flex-col items-start justify-between gap-6 border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-8 transition-shadow duration-300 hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)] dark:hover:shadow-[0_8px_24px_rgba(0,0,0,0.2)] md:flex-row md:items-center">
                        <div className="space-y-2">
                            <div className="flex items-center gap-3">
                                <Badge variant="neutral">推荐</Badge>
                                <span className="text-sm text-[#666666] dark:text-[#bcc5d3]">预计 30 分钟</span>
                            </div>
                            <h2 className="text-xl font-medium text-[#111111] dark:text-[#f4f7fb]">综合面试模拟</h2>
                            <p className="max-w-lg text-sm leading-relaxed text-[#666666] dark:text-[#bcc5d3]">
                                围绕 {state.targetRole} 场景进行完整模拟，重点强化 {state.weakestLabel}，并生成结构化复盘建议。
                            </p>
                        </div>

                        <Button
                            size="lg"
                            onClick={() => router.push('/interview/setup')}
                            className="group shrink-0 gap-2"
                        >
                            <Play className="h-4 w-4 transition-transform group-hover:scale-110" fill="currentColor" />
                            开始模拟
                        </Button>
                    </Card>
                </motion.div>

                {state.dataWarning && (
                    <motion.section variants={itemVariants} className="rounded-2xl border border-[#E8D9AE] bg-[#FFF9E8] px-4 py-3 text-sm text-[#7A5F00]">
                        {state.dataWarning}
                    </motion.section>
                )}

                <motion.section variants={itemVariants} className="grid grid-cols-1 gap-6 md:grid-cols-3">
                    <div className="col-span-1 space-y-6">
                        <h3 className="text-sm font-medium uppercase tracking-wider text-[#999999]">总览</h3>
                        <Card className="space-y-6 p-6 transition-shadow duration-300 hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)]">
                            <div>
                                <p className="mb-1 flex items-center gap-2 text-sm text-[#666666]">
                                    <Target className="h-4 w-4" />
                                    平均得分
                                </p>
                                <p className="text-3xl font-serif text-[#111111]">
                                    {state.averageScore ? state.averageScore.toFixed(1) : '--'}
                                    <span className="text-lg text-[#999999]">/100</span>
                                </p>
                                <p className="mt-2 flex items-center gap-1 text-xs text-[#2E6A45]">
                                    <TrendingUp className="h-3 w-3" />
                                    {formatWeeklyDelta(state.weeklyScoreDelta)}
                                </p>
                            </div>
                            <div className="h-px bg-[#E5E5E5]" />
                            <div>
                                <p className="mb-1 flex items-center gap-2 text-sm text-[#666666]">
                                    <Clock3 className="h-4 w-4" />
                                    练习时长
                                </p>
                                <p className="text-2xl font-serif text-[#111111]">
                                    {state.practiceHours ? state.practiceHours.toFixed(1) : '0.0'}
                                    <span className="text-base font-sans text-[#999999]"> 小时</span>
                                </p>
                            </div>
                        </Card>
                    </div>

                    <div className="col-span-1 space-y-6 md:col-span-2">
                        <div className="flex items-center justify-between">
                            <h3 className="text-sm font-medium uppercase tracking-wider text-[#999999]">最近记录</h3>
                            <button
                                onClick={() => router.push('/history')}
                                className="group inline-flex items-center gap-1 text-sm text-[#666666] transition hover:text-[#111111]"
                            >
                                查看全部
                                <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
                            </button>
                        </div>

                        <div className="space-y-3">
                            {!state.loading && state.recentSessions.map((session) => (
                                <motion.div
                                    key={session.key}
                                    whileHover={{ scale: 1.01 }}
                                    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                                >
                                    <Card className="group flex items-center justify-between p-4 transition-colors hover:border-[#111111]">
                                        <div className="min-w-0 pr-3">
                                            <p className="break-words font-medium text-[#111111] group-hover:underline decoration-[#E5E5E5] underline-offset-4">
                                                {session.title}
                                            </p>
                                            <p className="mt-1 text-sm text-[#666666]">{session.meta}</p>
                                        </div>
                                        <div className="shrink-0 text-right">
                                            <p className="text-xs text-[#999999]">得分</p>
                                            <p className="text-lg font-medium text-[#111111]">
                                                {session.score !== null ? session.score.toFixed(1) : '--'}
                                            </p>
                                        </div>
                                    </Card>
                                </motion.div>
                            ))}

                            {!state.loading && state.recentSessions.length === 0 && (
                                <Card className="border-dashed border-[#DADADA] bg-[#FCFCFB] px-5 py-8 text-center text-sm text-[#666666]">
                                    暂无历史会话，先开始一场新的模拟面试吧。
                                </Card>
                            )}

                            {state.loading && (
                                <Card className="p-5 text-sm text-[#666666]">
                                    正在加载最近会话数据...
                                </Card>
                            )}
                        </div>
                    </div>
                </motion.section>

                {false && reminders.length > 0 && (
                    <motion.section variants={itemVariants} className="space-y-4">
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <h3 className="text-sm font-medium uppercase tracking-wider text-[#999999]">行为提醒</h3>
                                <p className="mt-1 text-sm text-[#666666]">
                                    {reminderSummary?.current_streak_days
                                        ? `当前连续训练 ${reminderSummary.current_streak_days} 天`
                                        : '根据近期训练节奏和本周计划生成提醒'}
                                </p>
                            </div>
                        </div>
                        <div className="grid gap-3 md:grid-cols-2">
                            {reminders.map((item) => (
                                <Card key={item.id} className={`border px-5 py-4 shadow-sm ${reminderToneClasses(item.tone)}`}>
                                    <div className="flex items-start gap-3">
                                        <BellRing className="mt-0.5 h-4 w-4 shrink-0" />
                                        <div className="min-w-0">
                                            <h4 className="text-sm font-semibold">{item.title}</h4>
                                            <p className="mt-1 text-sm leading-6 opacity-90">{item.message}</p>
                                            {item.cta_href && item.cta_label ? (
                                                <button
                                                    type="button"
                                                    onClick={() => router.push(item.cta_href || '/dashboard')}
                                                    className="mt-3 inline-flex items-center gap-1 text-sm font-medium underline underline-offset-4"
                                                >
                                                    {item.cta_label}
                                                    <ArrowRight className="h-3.5 w-3.5" />
                                                </button>
                                            ) : null}
                                        </div>
                                    </div>
                                </Card>
                            ))}
                        </div>
                    </motion.section>
                )}
            </motion.div>
        </div>
    )
}

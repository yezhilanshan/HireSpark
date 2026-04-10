'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowRight, Clock3, Play, Target, TrendingUp } from 'lucide-react'
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

function formatSessionMeta(record: InterviewRecord): string {
    const timeValue = toTimestamp(record.created_at || record.start_time)
    const time = timeValue ? new Date(timeValue) : null

    let dayLabel = '最近'
    if (time) {
        const todayStart = new Date()
        todayStart.setHours(0, 0, 0, 0)
        const targetDay = new Date(time)
        targetDay.setHours(0, 0, 0, 0)
        const delta = Math.floor((todayStart.getTime() - targetDay.getTime()) / (1000 * 60 * 60 * 24))
        if (delta === 0) {
            dayLabel = '今天'
        } else if (delta === 1) {
            dayLabel = '昨天'
        } else {
            dayLabel = `${time.getMonth() + 1}/${time.getDate()}`
        }
    }

    const duration = Math.max(0, Number(record.duration || 0))
    if (duration <= 0) {
        return dayLabel
    }

    const minutes = Math.round(duration / 60)
    if (minutes <= 0) {
        return `${dayLabel} ${duration} 秒`
    }
    return `${dayLabel} ${minutes} 分钟`
}

function buildSessionTitle(record: InterviewRecord, index: number): string {
    const risk = (record.risk_level || '').toUpperCase()
    if (risk === 'LOW') return '行为稳定性检查'
    if (risk === 'MEDIUM') return '表达执行力优化'
    if (risk === 'HIGH') return '压力恢复训练'

    const suffix = record.interview_id ? `#${record.interview_id.slice(-4)}` : `#${index + 1}`
    return `综合面试 ${suffix}`
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
    const [state, setState] = useState<DashboardState>(INITIAL_STATE)

    useEffect(() => {
        let cancelled = false

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
                .slice(0, 3)
                .map((item, index) => ({
                    key: item.interview_id || `${item.id || index}`,
                    title: buildSessionTitle(item, index),
                    meta: formatSessionMeta(item),
                    score: getStructuredScore(item),
                }))

            const parsed = resume?.resume?.parsed_data
            const candidateName = parsed?.basic_info?.name?.trim() || extractNameFromRawText(parsed?.raw_text) || '候选人'

            const weeklyScoreDelta = thisWeekScores.length && previousWeekScores.length
                ? average(thisWeekScores) - average(previousWeekScores)
                : 0

            if (cancelled) return

            setState({
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
            })
        }

        load().catch(() => {
            if (!cancelled) {
                setState((prev) => ({ ...prev, loading: false, dataWarning: '数据同步失败，请稍后重试。' }))
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
                        <div className="hidden items-center gap-2 rounded-full border border-[#E5E5E5] bg-white px-3 py-1.5 text-xs text-[#999999] shadow-sm md:flex">
                            <span className="font-medium">快捷键</span>
                            <kbd className="rounded bg-[#F5F5F5] px-1.5 py-0.5 text-[#111111]">Ctrl K</kbd>
                        </div>
                        <div className="flex items-center gap-4">
                            <div className="hidden text-right sm:block">
                                <p className="text-sm font-medium text-[#111111]">{state.targetRole}</p>
                                <p className="text-xs text-[#999999]">目标岗位</p>
                            </div>
                            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#EBE9E0] font-medium text-[#111111]">
                                {avatarInitial}
                            </div>
                        </div>
                    </div>
                </motion.header>

                <motion.div variants={itemVariants}>
                    <Card className="flex flex-col items-start justify-between gap-6 border-[#E5E5E5] bg-white p-8 transition-shadow duration-300 hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)] md:flex-row md:items-center">
                        <div className="space-y-2">
                            <div className="flex items-center gap-3">
                                <Badge variant="neutral">推荐</Badge>
                                <span className="text-sm text-[#666666]">预计 30 分钟</span>
                            </div>
                            <h2 className="text-xl font-medium text-[#111111]">综合面试模拟</h2>
                            <p className="max-w-lg text-sm leading-relaxed text-[#666666]">
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
                                <motion.div key={session.key} whileHover={{ scale: 1.01 }} transition={{ type: 'spring', stiffness: 400, damping: 30 }}>
                                    <Card className="group flex items-center justify-between p-4 transition-colors hover:border-[#111111]">
                                        <div className="min-w-0 pr-3">
                                            <p className="break-words font-medium text-[#111111] group-hover:underline decoration-[#E5E5E5] underline-offset-4">
                                                {session.title}
                                            </p>
                                            <p className="mt-1 text-xs text-[#666666]">{session.meta}</p>
                                        </div>
                                        <div className="shrink-0 text-right">
                                            <p className="text-lg font-serif text-[#111111]">{session.score === null ? '--' : session.score.toFixed(1)}</p>
                                            <p className="text-xs text-[#999999]">得分</p>
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
            </motion.div>
        </div>
    )
}

'use client'

import Link from 'next/link'
import { Suspense, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useSearchParams } from 'next/navigation'
import {
    AlertCircle,
    ArrowRight,
    BarChart3,
    Camera,
    Clock3,
    Eye,
    Gauge,
    MessageSquare,
    Mic,
    ShieldCheck,
    Target,
    TrendingUp,
    Users,
    Volume2,
} from 'lucide-react'
import PersistentSidebar from '@/components/PersistentSidebar'

const BACKEND_API_BASE = (process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000').replace(/\/$/, '')

type StructuredDimension = {
    key: string
    label: string
    score: number
}

type ImmediateReport = {
    interview_id: string
    summary: {
        duration_seconds: number
    }
    anti_cheat: {
        risk_level: string
        max_probability: number
        avg_probability: number
        events_count: number
        event_type_breakdown?: EventTypeCount[]
        top_risk_events?: RiskEvent[]
        statistics?: CameraStatistics
    }
    structured_evaluation: {
        status: string
        status_message: string
        overall_score: number | null
        level: string | null
        dimension_scores: StructuredDimension[]
    }
    content_performance?: ContentPerformance
    speech_performance?: SpeechPerformance
    camera_performance?: CameraPerformance
    next_steps?: {
        replay_url?: string
    }
}

type RiskEvent = {
    event_type: string
    score: number
    description: string
    timestamp: number
}

type EventTypeCount = {
    event_type: string
    count: number
}

type CameraStatistics = {
    total_deviations: number
    total_mouth_open: number
    total_multi_person: number
    off_screen_ratio: number
    frames_processed?: number
}

type WeakDimension = {
    key: string
    label: string
    avg_score: number
    sample_count: number
    reasons: string[]
    reason_tags?: string[]
}

type QuestionEvidence = {
    turn_id: string
    round_type: string
    question_excerpt: string
    answer_excerpt: string
    overall_score: number
    weak_dimensions: Array<{
        key: string
        label: string
        score: number
        reason: string
        reason_tags?: string[]
    }>
    reason_tags?: string[]
    evidence_tags: string[]
    trace_source: string
}

type ContentPerformance = {
    status: string
    status_message: string
    weak_dimensions: WeakDimension[]
    question_evidence: QuestionEvidence[]
    scoring_basis: {
        overall_formula: string
        question_formula: string
        sample_size: number
    }
}

type SpeechPerformance = {
    status: string
    status_message: string
    dimensions: Array<{
        key: string
        label: string
        score: number
    }>
    summary: {
        avg_speech_rate_wpm?: number
        avg_fillers_per_100_words?: number
        avg_pause_anomaly_ratio?: number
        avg_long_pause_count?: number
        samples?: number
    }
    evidence_samples: Array<{
        turn_id: string
        transcript_excerpt: string
        speech_rate_wpm: number
        fillers_per_100_words: number
        pause_anomaly_ratio: number
        long_pause_count: number
        token_count: number
    }>
    diagnosis: string[]
}

type CameraPerformance = {
    status: string
    status_message: string
    overall_score: number
    focus_score: number
    compliance_score: number
    anti_cheat_score: number
    statistics: CameraStatistics
    event_type_breakdown: EventTypeCount[]
    top_risk_events: RiskEvent[]
    notes: string[]
}

type ApiResult = {
    success: boolean
    report?: ImmediateReport
    error?: string
}

function formatDuration(seconds = 0) {
    const safe = Math.max(0, Math.floor(seconds))
    const min = Math.floor(safe / 60)
    const sec = safe % 60
    return min > 0 ? `${min}分${sec}秒` : `${sec}秒`
}

function riskTone(level: string) {
    const normalized = String(level || '').toUpperCase()
    if (normalized === 'HIGH') return 'bg-[#FCEBE9] text-[#9D3A2E]'
    if (normalized === 'MEDIUM') return 'bg-[#FFF4E5] text-[#8B5E1A]'
    return 'bg-[#EAF5ED] text-[#2F6B45]'
}

function eventLabel(eventType: string) {
    const normalized = String(eventType || '').toLowerCase()
    if (normalized === 'gaze_deviation') return '视线偏离'
    if (normalized === 'mouth_open') return '异常口型'
    if (normalized === 'multi_person') return '多人同框'
    return normalized || '未知事件'
}

function formatNum(value: unknown, digits = 1, fallback = '--') {
    const num = Number(value)
    return Number.isFinite(num) ? num.toFixed(digits) : fallback
}

function formatEventTime(value: unknown) {
    const num = Number(value)
    if (!Number.isFinite(num)) return '--'
    if (num > 1_000_000) {
        const date = new Date(num * 1000)
        if (!Number.isNaN(date.getTime())) {
            return date.toLocaleTimeString('zh-CN', { hour12: false })
        }
    }
    return `${num.toFixed(1)} 秒`
}

function reasonTagTone(tag: string) {
    if (tag === '技术') return 'bg-[#E7F0FF] text-[#2C4A7A]'
    if (tag === '表达') return 'bg-[#FDEFE5] text-[#8A5425]'
    return 'bg-[#ECEBE8] text-[#565451]'
}

function ReportPageContent() {
    const searchParams = useSearchParams()
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [report, setReport] = useState<ImmediateReport | null>(null)
    const interviewId = (searchParams.get('interviewId') || '').trim()

    useEffect(() => {
        const load = async () => {
            try {
                setLoading(true)
                setError('')
                const endpoint = interviewId
                    ? `${BACKEND_API_BASE}/api/report/interview/${encodeURIComponent(interviewId)}`
                    : `${BACKEND_API_BASE}/api/report/latest`
                const res = await fetch(endpoint, { cache: 'no-store' })
                const data: ApiResult = await res.json()
                if (!res.ok || !data.success || !data.report) {
                    throw new Error(data.error || '获取报告失败')
                }
                setReport(data.report)
            } catch (e) {
                setReport(null)
                setError(e instanceof Error ? e.message : '获取报告失败')
            } finally {
                setLoading(false)
            }
        }
        void load()
    }, [interviewId])

    const topDimensions = useMemo(() => {
        return [...(report?.structured_evaluation?.dimension_scores || [])]
            .sort((a, b) => Number(b.score || 0) - Number(a.score || 0))
            .slice(0, 6)
    }, [report])

    const dimensionScale = useMemo(() => {
        const values = topDimensions.map((item) => Number(item.score || 0))
        return Math.max(1, ...values)
    }, [topDimensions])

    const radarDimensions = useMemo(() => {
        const weakSource = (report?.content_performance?.weak_dimensions || []).slice(0, 5)
        if (weakSource.length > 0) {
            return weakSource.map((item) => ({
                key: item.key,
                label: item.label,
                score: Number(item.avg_score || 0),
            }))
        }
        return (report?.structured_evaluation?.dimension_scores || []).slice(0, 5).map((item) => ({
            key: item.key,
            label: item.label,
            score: Number(item.score || 0),
        }))
    }, [report])

    if (loading) {
        return (
            <div className="flex min-h-screen">
                <PersistentSidebar />
                <main className="flex-1 overflow-y-auto">
                    <div className="mx-auto max-w-4xl px-6 py-8">
                        <section className="rounded-2xl border border-[#E5E5E5] bg-white p-8 text-center shadow-sm">
                            <p className="text-sm text-[#666666]">报告加载中...</p>
                        </section>
                    </div>
                </main>
            </div>
        )
    }

    if (error || !report) {
        return (
            <div className="flex min-h-screen">
                <PersistentSidebar />
                <main className="flex-1 overflow-y-auto">
                    <div className="mx-auto max-w-4xl px-6 py-8">
                        <section className="rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                            <div className="flex items-center gap-2 text-[#8A3B3B]"><AlertCircle className="h-5 w-5" />报告加载失败</div>
                            <p className="mt-2 text-sm text-[#666666]">{error || '未知错误'}</p>
                            <div className="mt-4 flex flex-wrap gap-3">
                                <Link href="/history" className="inline-flex items-center gap-2 rounded-lg border border-[#E5E5E5] px-4 py-2 text-sm font-medium text-[#111111] hover:bg-[#F5F5F5]">
                                    返回历史记录
                                </Link>
                            </div>
                        </section>
                    </div>
                </main>
            </div>
        )
    }

    const replayUrl = report.next_steps?.replay_url || `/replay?interviewId=${encodeURIComponent(report.interview_id)}`
    const contentPerf = report.content_performance
    const speechPerf = report.speech_performance
    const cameraPerf = report.camera_performance
    const cameraStats = cameraPerf?.statistics || report.anti_cheat.statistics
    const cameraBreakdown = cameraPerf?.event_type_breakdown || report.anti_cheat.event_type_breakdown || []
    const cameraTopEvents = cameraPerf?.top_risk_events || report.anti_cheat.top_risk_events || []
    const riskHeatValue = Math.max(0, Math.min(100, Number(report.anti_cheat.max_probability || 0)))
    const riskHeatClass = riskHeatValue >= 60
        ? '[&::-webkit-progress-value]:bg-[#B84436] [&::-moz-progress-bar]:bg-[#B84436]'
        : riskHeatValue >= 30
            ? '[&::-webkit-progress-value]:bg-[#C17C2D] [&::-moz-progress-bar]:bg-[#C17C2D]'
            : '[&::-webkit-progress-value]:bg-[#3E7657] [&::-moz-progress-bar]:bg-[#3E7657]'

    return (
        <div className="flex min-h-screen">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-6xl px-6 py-8 space-y-6">
                    <section className="rounded-3xl border border-[#E5E5E5] bg-[#FAF9F6] p-6 shadow-sm sm:p-8">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <span className="inline-flex items-center gap-2 rounded-full border border-[#E5E5E5] bg-white px-4 py-2 text-sm text-[#111111]">
                        <ShieldCheck className="h-4 w-4" /> 即时报告
                    </span>
                    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${riskTone(report.anti_cheat.risk_level)}`}>
                        风险 {(report.anti_cheat.risk_level || 'LOW').toUpperCase()}
                    </span>
                </div>
                <h1 className="mt-4 text-3xl tracking-tight text-[#111111] sm:text-4xl">本场面试报告</h1>
                <p className="mt-2 text-sm leading-6 text-[#666666]">用于回看本场结果指标，和“面试复盘（视频+文本锚点）”入口分离。</p>

                <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <MetricCard title="结构化总分" value={report.structured_evaluation.overall_score == null ? '--' : report.structured_evaluation.overall_score.toFixed(1)} icon={<Target className="h-3.5 w-3.5" />} />
                    <MetricCard title="评分状态" value={report.structured_evaluation.status || 'unknown'} />
                    <MetricCard title="风险事件数" value={String(report.anti_cheat.events_count || 0)} icon={<TrendingUp className="h-3.5 w-3.5" />} />
                    <MetricCard title="会话时长" value={formatDuration(report.summary.duration_seconds)} icon={<Clock3 className="h-3.5 w-3.5" />} />
                </div>

                <div className="mt-5 rounded-2xl border border-[#E5E5E5] bg-white p-4">
                    <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-medium text-[#111111]">风险热度条</p>
                        <span className="text-sm text-[#666666]">{formatNum(riskHeatValue)}%</span>
                    </div>
                    <progress
                        className={`mt-2 h-3 w-full overflow-hidden rounded-full [appearance:none] [&::-webkit-progress-bar]:bg-[#ECE9E1] ${riskHeatClass}`}
                        value={riskHeatValue}
                        max={100}
                    />
                    <p className="mt-2 text-xs text-[#888888]">依据：max_probability（防作弊风险峰值）</p>
                </div>
            </section>

            <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                <h2 className="text-xl text-[#111111]">结构化评分维度</h2>
                <p className="mt-2 text-sm text-[#666666]">{report.structured_evaluation.status_message || '暂无状态信息'}</p>
                <div className="mt-4 grid gap-3">
                    {topDimensions.length === 0 ? (
                        <p className="rounded-xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] p-4 text-sm text-[#666666]">暂无维度评分。</p>
                    ) : (
                        topDimensions.map((item) => (
                            <div key={item.key} className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-3">
                                <div className="flex items-center justify-between gap-3">
                                    <p className="text-sm font-medium text-[#111111]">{item.label}</p>
                                    <span className="rounded-full border border-[#E5E5E5] bg-white px-3 py-1 text-xs text-[#111111]">
                                        {Number(item.score || 0).toFixed(1)}
                                    </span>
                                </div>
                                <progress
                                    className="mt-2 h-2 w-full overflow-hidden rounded-full [appearance:none] [&::-webkit-progress-bar]:bg-[#EDEBE4] [&::-webkit-progress-value]:bg-[#5D6B8A] [&::-moz-progress-bar]:bg-[#5D6B8A]"
                                    value={Math.max(0, Number(item.score || 0))}
                                    max={dimensionScale}
                                />
                            </div>
                        ))
                    )}
                </div>
            </section>

            <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                <div className="flex items-center gap-2">
                    <Target className="h-5 w-5 text-[#556987]" />
                    <h2 className="text-xl text-[#111111]">能力雷达（弱项优先）</h2>
                </div>
                <p className="mt-2 text-sm text-[#666666]">雷达图用于快速定位本场优先改进维度。</p>
                <div className="mt-4">
                    <RadarSnapshot dimensions={radarDimensions} />
                </div>
            </section>

            <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                <div className="flex items-center gap-2">
                    <MessageSquare className="h-5 w-5 text-[#556987]" />
                    <h2 className="text-xl text-[#111111]">内容表现与可追溯依据</h2>
                </div>
                <p className="mt-2 text-sm text-[#666666]">{contentPerf?.status_message || '暂无内容表现依据。'}</p>

                {contentPerf?.status === 'ready' ? (
                    <>
                        <div className="mt-4 rounded-xl border border-[#E5E5E5] bg-[#F8F7F3] p-4 text-xs text-[#444444]">
                            <p><span className="font-medium">总分公式：</span>{contentPerf.scoring_basis?.overall_formula || '--'}</p>
                            <p className="mt-1"><span className="font-medium">单题公式：</span>{contentPerf.scoring_basis?.question_formula || '--'}</p>
                            <p className="mt-1"><span className="font-medium">样本数：</span>{contentPerf.scoring_basis?.sample_size ?? 0}</p>
                        </div>

                        <div className="mt-4 grid gap-3 md:grid-cols-2">
                            {(contentPerf.weak_dimensions || []).slice(0, 4).map((dim) => (
                                <div key={dim.key} className="rounded-xl border border-[#E5E5E5] p-3">
                                    <div className="flex items-center justify-between gap-2">
                                        <p className="text-sm font-medium text-[#111111]">{dim.label}</p>
                                        <span className="rounded-full bg-[#F3EFE4] px-2 py-1 text-xs text-[#6A5A2B]">
                                            均分 {formatNum(dim.avg_score)}
                                        </span>
                                    </div>
                                    <p className="mt-1 text-xs text-[#777777]">样本 {dim.sample_count}</p>
                                    {(dim.reason_tags || []).length > 0 && (
                                        <div className="mt-2 flex flex-wrap gap-1.5">
                                            {(dim.reason_tags || []).map((tag) => (
                                                <span key={`${dim.key}-${tag}`} className={`rounded-full px-2 py-0.5 text-xs ${reasonTagTone(tag)}`}>
                                                    {tag}
                                                </span>
                                            ))}
                                        </div>
                                    )}
                                    {(dim.reasons || []).slice(0, 1).map((reason, index) => (
                                        <p key={`${dim.key}-${index}`} className="mt-2 text-sm text-[#555555]">依据：{reason}</p>
                                    ))}
                                </div>
                            ))}
                        </div>

                        <div className="mt-5 rounded-2xl border border-[#E5E5E5] bg-[#FCFBF8] p-4">
                            <div className="flex items-center gap-2">
                                <BarChart3 className="h-4 w-4 text-[#556987]" />
                                <p className="text-sm font-medium text-[#111111]">证据时间轴（按单题得分从低到高）</p>
                            </div>
                            <div className="mt-3">
                                {(contentPerf.question_evidence || []).slice(0, 6).map((item, index, arr) => (
                                    <div key={`${item.turn_id}-${item.round_type}`} className="relative pb-4 pl-9">
                                        {index < arr.length - 1 && (
                                            <span className="absolute left-[13px] top-7 h-[calc(100%-8px)] w-px bg-[#DDD7CA]" />
                                        )}
                                        <span className="absolute left-0 top-1.5 flex h-7 w-7 items-center justify-center rounded-full border border-[#D8D2C6] bg-white text-xs text-[#555555]">
                                            {index + 1}
                                        </span>
                                        <div className="rounded-xl border border-[#E5E5E5] bg-white p-4">
                                            <div className="flex flex-wrap items-center justify-between gap-2">
                                                <span className="rounded-full bg-white px-2.5 py-1 text-xs text-[#555555]">{item.round_type || 'unknown'}</span>
                                                <span className="rounded-full bg-[#FDECEC] px-2.5 py-1 text-xs text-[#8A3B3B]">单题分 {formatNum(item.overall_score)}</span>
                                            </div>
                                            <p className="mt-2 text-sm font-medium text-[#111111]">Q：{item.question_excerpt || '暂无题干'}</p>
                                            <p className="mt-1 text-sm text-[#555555]">A：{item.answer_excerpt || '暂无回答文本'}</p>
                                            {(item.reason_tags || []).length > 0 && (
                                                <div className="mt-2 flex flex-wrap gap-1.5">
                                                    {(item.reason_tags || []).map((tag) => (
                                                        <span key={`${item.turn_id}-${tag}`} className={`rounded-full px-2 py-0.5 text-xs ${reasonTagTone(tag)}`}>
                                                            {tag}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}
                                            <div className="mt-2 flex flex-wrap gap-2">
                                                {(item.weak_dimensions || []).map((dim) => (
                                                    <span key={`${item.turn_id}-${dim.key}`} className="rounded-full border border-[#E5E5E5] bg-white px-2.5 py-1 text-xs text-[#555555]">
                                                        {dim.label} {formatNum(dim.score)}
                                                    </span>
                                                ))}
                                            </div>
                                            {(item.evidence_tags || []).length > 0 && (
                                                <div className="mt-2 flex flex-wrap gap-2">
                                                    {(item.evidence_tags || []).map((tag, tagIndex) => (
                                                        <span key={`${item.turn_id}-tag-${tagIndex}`} className="rounded-full bg-[#EFEDE8] px-2 py-1 text-xs text-[#666666]">
                                                            {tag}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}
                                            <p className="mt-2 text-xs text-[#888888]">来源：{item.trace_source || 'interview_evaluations'}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </>
                ) : (
                    <p className="mt-4 rounded-xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] p-4 text-sm text-[#666666]">内容表现证据暂不可用。</p>
                )}
            </section>

            <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                <div className="flex items-center gap-2">
                    <Mic className="h-5 w-5 text-[#556987]" />
                    <h2 className="text-xl text-[#111111]">语音表达分析</h2>
                </div>
                <p className="mt-2 text-sm text-[#666666]">{speechPerf?.status_message || '暂无语音分析。'}</p>

                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <InsightMetric title="平均语速" value={`${formatNum(speechPerf?.summary?.avg_speech_rate_wpm)} wpm`} icon={<Gauge className="h-4 w-4" />} />
                    <InsightMetric title="口头词/百词" value={formatNum(speechPerf?.summary?.avg_fillers_per_100_words, 2)} icon={<Volume2 className="h-4 w-4" />} />
                    <InsightMetric title="停顿异常比" value={`${formatNum(Number(speechPerf?.summary?.avg_pause_anomaly_ratio || 0) * 100)}%`} icon={<BarChart3 className="h-4 w-4" />} />
                    <InsightMetric title="语音样本数" value={String(speechPerf?.summary?.samples || 0)} icon={<Mic className="h-4 w-4" />} />
                </div>

                {(speechPerf?.dimensions || []).length > 0 && (
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                        {(speechPerf?.dimensions || []).map((dim) => (
                            <div key={dim.key} className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-3">
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-sm font-medium text-[#111111]">{dim.label}</p>
                                    <span className="rounded-full bg-white px-2 py-1 text-xs text-[#555555]">{formatNum(dim.score)}</span>
                                </div>
                                <progress
                                    className="mt-2 h-2 w-full overflow-hidden rounded-full [appearance:none] [&::-webkit-progress-bar]:bg-[#ECE9E1] [&::-webkit-progress-value]:bg-[#4C6A8A] [&::-moz-progress-bar]:bg-[#4C6A8A]"
                                    value={Math.max(0, Number(dim.score || 0))}
                                    max={100}
                                />
                            </div>
                        ))}
                    </div>
                )}

                {(speechPerf?.diagnosis || []).length > 0 && (
                    <div className="mt-4 rounded-xl border border-[#E5E5E5] bg-[#F8F7F3] p-4 text-sm text-[#555555]">
                        {(speechPerf?.diagnosis || []).map((item, index) => (
                            <p key={`diag-${index}`} className={index === 0 ? '' : 'mt-1'}>{item}</p>
                        ))}
                    </div>
                )}

                {(speechPerf?.evidence_samples || []).length > 0 && (
                    <div className="mt-4 space-y-3">
                        {(speechPerf?.evidence_samples || []).slice(0, 4).map((sample) => (
                            <div key={sample.turn_id || sample.transcript_excerpt} className="rounded-xl border border-[#E5E5E5] p-3">
                                <p className="text-sm text-[#111111]">文本样本：{sample.transcript_excerpt || '暂无转写文本'}</p>
                                <div className="mt-2 flex flex-wrap gap-2 text-xs text-[#666666]">
                                    <span className="rounded-full bg-[#F0EEEA] px-2 py-1">语速 {formatNum(sample.speech_rate_wpm)} wpm</span>
                                    <span className="rounded-full bg-[#F0EEEA] px-2 py-1">口头词 {formatNum(sample.fillers_per_100_words, 2)}/百词</span>
                                    <span className="rounded-full bg-[#F0EEEA] px-2 py-1">长停顿 {sample.long_pause_count}</span>
                                    <span className="rounded-full bg-[#F0EEEA] px-2 py-1">停顿异常比 {formatNum(Number(sample.pause_anomaly_ratio || 0) * 100)}%</span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </section>

            <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                <div className="flex items-center gap-2">
                    <Camera className="h-5 w-5 text-[#556987]" />
                    <h2 className="text-xl text-[#111111]">镜头前表现</h2>
                </div>
                <p className="mt-2 text-sm text-[#666666]">{cameraPerf?.status_message || '基于防作弊事件与统计指标生成。'}</p>

                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <InsightMetric title="镜头稳定分" value={formatNum(cameraPerf?.focus_score)} icon={<Eye className="h-4 w-4" />} />
                    <InsightMetric title="规范性分" value={formatNum(cameraPerf?.compliance_score)} icon={<Users className="h-4 w-4" />} />
                    <InsightMetric title="屏幕外注视" value={`${formatNum(cameraStats?.off_screen_ratio)}%`} icon={<TrendingUp className="h-4 w-4" />} />
                    <InsightMetric title="多人同框次数" value={String(cameraStats?.total_multi_person || 0)} icon={<Users className="h-4 w-4" />} />
                </div>

                {(cameraPerf?.notes || []).length > 0 && (
                    <div className="mt-4 rounded-xl border border-[#E5E5E5] bg-[#F8F7F3] p-4 text-sm text-[#555555]">
                        {(cameraPerf?.notes || []).map((note, index) => (
                            <p key={`camera-note-${index}`} className={index === 0 ? '' : 'mt-1'}>{note}</p>
                        ))}
                    </div>
                )}

                {cameraBreakdown.length > 0 && (
                    <div className="mt-4 flex flex-wrap gap-2">
                        {cameraBreakdown.map((item) => (
                            <span key={`${item.event_type}-${item.count}`} className="inline-flex items-center gap-1 rounded-full border border-[#E5E5E5] bg-white px-2.5 py-1 text-xs text-[#555555]">
                                {eventLabel(item.event_type)} {item.count}
                            </span>
                        ))}
                    </div>
                )}

                {cameraTopEvents.length > 0 && (
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                        {cameraTopEvents.slice(0, 4).map((event, index) => (
                            <div key={`${event.event_type}-${event.timestamp}-${index}`} className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-3">
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-sm font-medium text-[#111111]">{eventLabel(event.event_type)}</p>
                                    <span className="rounded-full bg-white px-2 py-1 text-xs text-[#666666]">{formatNum(event.score)}</span>
                                </div>
                                <p className="mt-1 text-sm text-[#555555]">{event.description || '无补充描述'}</p>
                                <p className="mt-1 text-xs text-[#888888]">发生时间：{formatEventTime(event.timestamp)}</p>
                            </div>
                        ))}
                    </div>
                )}
            </section>

            <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                <div className="flex flex-wrap gap-3">
                    <Link href={replayUrl} className="inline-flex items-center gap-2 rounded-xl bg-[#111111] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#222222]">
                        进入面试复盘（视频+锚点）
                        <ArrowRight className="h-4 w-4" />
                    </Link>
                    <Link href="/history" className="inline-flex items-center gap-2 rounded-xl border border-[#E5E5E5] px-4 py-2.5 text-sm font-medium text-[#111111] hover:bg-[#F5F5F5]">
                        返回历史记录
                    </Link>
                </div>
            </section>
        </div>
    </main>
</div>
    )
}

function ReportPageFallback() {
    return (
        <div className="flex min-h-screen">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-4xl px-6 py-8">
                    <section className="rounded-2xl border border-[#E5E5E5] bg-white p-8 text-center shadow-sm">
                        <p className="text-sm text-[#666666]">报告加载中...</p>
                    </section>
                </div>
            </main>
        </div>
    )
}

export default function ReportPage() {
    return (
        <Suspense fallback={<ReportPageFallback />}>
            <ReportPageContent />
        </Suspense>
    )
}

function MetricCard({ title, value, icon }: { title: string; value: string; icon?: ReactNode }) {
    return (
        <div className="rounded-2xl border border-[#E5E5E5] bg-white p-4">
            <p className="text-xs uppercase tracking-[0.12em] text-[#999999]">{title}</p>
            <p className="mt-2 flex items-center gap-1 text-2xl font-semibold text-[#111111]">{value}{icon}</p>
        </div>
    )
}

function InsightMetric({ title, value, icon }: { title: string; value: string; icon?: ReactNode }) {
    return (
        <div className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-3">
            <p className="text-xs text-[#888888]">{title}</p>
            <p className="mt-2 flex items-center gap-1 text-lg font-semibold text-[#111111]">{value}{icon}</p>
        </div>
    )
}

function RadarSnapshot({ dimensions }: { dimensions: Array<{ key: string; label: string; score: number }> }) {
    const normalized = (dimensions || []).slice(0, 6)
    if (normalized.length < 3) {
        return <p className="rounded-xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] p-4 text-sm text-[#666666]">维度数据不足，无法绘制雷达图。</p>
    }

    const size = 220
    const center = size / 2
    const radius = 74
    const total = normalized.length

    const pointAt = (index: number, ratio: number) => {
        const angle = (-Math.PI / 2) + (Math.PI * 2 * index / total)
        return {
            x: center + radius * ratio * Math.cos(angle),
            y: center + radius * ratio * Math.sin(angle),
        }
    }

    const axisPoints = normalized.map((item, index) => {
        const score = Math.max(0, Math.min(100, Number(item.score || 0)))
        const valuePoint = pointAt(index, score / 100)
        const outerPoint = pointAt(index, 1)
        const labelPoint = pointAt(index, 1.22)
        return {
            ...item,
            score,
            valuePoint,
            outerPoint,
            labelPoint,
        }
    })

    const polygonPoints = axisPoints.map((item) => `${item.valuePoint.x.toFixed(1)},${item.valuePoint.y.toFixed(1)}`).join(' ')
    const levelPolygons = [0.25, 0.5, 0.75, 1].map((ratio) => {
        const points = normalized.map((_, index) => {
            const point = pointAt(index, ratio)
            return `${point.x.toFixed(1)},${point.y.toFixed(1)}`
        }).join(' ')
        return { ratio, points }
    })

    return (
        <div className="rounded-2xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium text-[#111111]">多维能力雷达</p>
                <p className="text-xs text-[#777777]">分值范围 0-100</p>
            </div>

            <div className="mt-4 flex flex-col gap-4 md:flex-row md:items-start">
                <svg viewBox="0 0 220 220" className="h-[220px] w-[220px] shrink-0">
                    {levelPolygons.map((item) => (
                        <polygon key={`grid-${item.ratio}`} points={item.points} fill="none" stroke="#DDD7CA" strokeWidth="1" />
                    ))}
                    {axisPoints.map((item) => (
                        <line key={`axis-${item.key}`} x1={center} y1={center} x2={item.outerPoint.x} y2={item.outerPoint.y} stroke="#E6E1D7" strokeWidth="1" />
                    ))}
                    <polygon points={polygonPoints} fill="rgba(76, 106, 138, 0.18)" stroke="#4C6A8A" strokeWidth="2" />
                    {axisPoints.map((item) => (
                        <circle key={`point-${item.key}`} cx={item.valuePoint.x} cy={item.valuePoint.y} r="3" fill="#4C6A8A" />
                    ))}
                    {axisPoints.map((item) => (
                        <text
                            key={`label-${item.key}`}
                            x={item.labelPoint.x}
                            y={item.labelPoint.y}
                            textAnchor={item.labelPoint.x < center - 8 ? 'end' : item.labelPoint.x > center + 8 ? 'start' : 'middle'}
                            dominantBaseline="middle"
                            fontSize="11"
                            fill="#555555"
                        >
                            {item.label.length > 8 ? `${item.label.slice(0, 8)}…` : item.label}
                        </text>
                    ))}
                </svg>

                <div className="grid flex-1 gap-2 sm:grid-cols-2">
                    {axisPoints.map((item) => (
                        <div key={`legend-${item.key}`} className="rounded-xl border border-[#E5E5E5] bg-white px-3 py-2">
                            <p className="text-xs text-[#777777]">{item.label}</p>
                            <p className="mt-1 text-sm font-semibold text-[#111111]">{formatNum(item.score)}</p>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}

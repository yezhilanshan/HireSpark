'use client'

import Link from 'next/link'
import { Suspense, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useSearchParams } from 'next/navigation'
import { AlertCircle, ArrowRight, Clock3, ShieldCheck, Target, TrendingUp } from 'lucide-react'
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
    }
    structured_evaluation: {
        status: string
        status_message: string
        overall_score: number | null
        level: string | null
        dimension_scores: StructuredDimension[]
    }
    next_steps?: {
        replay_url?: string
    }
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
                            </div>
                        ))
                    )}
                </div>
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

'use client'

import Link from 'next/link'
import { Suspense, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { AlertTriangle, ArrowRight, CheckCircle, CheckCircle2, Clock3, FileText, Radar, type LucideIcon } from 'lucide-react'
import PersistentSidebar from '@/components/PersistentSidebar'
import { getBackendBaseUrl } from '@/lib/backend'

const BACKEND_API_BASE = getBackendBaseUrl()

type GrowthReport = {
    summary: {
        overall_score: number | null
        interview_count: number
        duration_seconds: number
        dominant_round: string
    }
    strengths: string[]
    weaknesses: string[]
    improvement_plan: Array<{
        focus: string
        action: string
        target: string
    }>
}

type ApiResult = {
    success: boolean
    report: GrowthReport | null
    message?: string
    error?: string
}

type ImmediateReportApiResult = {
    success: boolean
    report?: {
        final_score?: {
            overall_score?: number | null
        }
        structured_evaluation?: {
            overall_score?: number | null
            round_aggregation?: {
                interview_stability?: {
                    overall_score_stable?: number | null
                }
            }
        }
        evaluation_v2?: {
            fusion?: {
                overall_score?: number | null
            }
        }
    } | null
}

function toNullableScore(value: unknown): number | null {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
}

function resolveImmediateReportOverallScore(payload: ImmediateReportApiResult | null | undefined): number | null {
    const reportPayload = payload?.report
    if (!reportPayload) return null

    const finalScore = toNullableScore(reportPayload.final_score?.overall_score)
    if (finalScore != null) return finalScore

    const stableScore = toNullableScore(
        reportPayload.structured_evaluation?.round_aggregation?.interview_stability?.overall_score_stable,
    )
    if (stableScore != null) return stableScore

    const fusionScore = toNullableScore(reportPayload.evaluation_v2?.fusion?.overall_score)
    if (fusionScore != null) return fusionScore

    return toNullableScore(reportPayload.structured_evaluation?.overall_score)
}

const roundNameMap: Record<string, string> = {
    technical: '技术基础面',
    project: '项目深度面',
    system_design: '系统设计面',
    hr: 'HR 综合面',
}

function formatDuration(seconds: number): string {
    const safe = Math.max(0, Number.isFinite(seconds) ? Math.floor(seconds) : 0)
    const min = Math.floor(safe / 60)
    const sec = safe % 60
    if (min <= 0) return `${sec}秒`
    return `${min}分${sec}秒`
}

function ReviewPageContent() {
    const searchParams = useSearchParams()
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [report, setReport] = useState<GrowthReport | null>(null)
    const [reportOverallScore, setReportOverallScore] = useState<number | null>(null)
    const interviewId = (searchParams.get('interviewId') || '').trim()

    useEffect(() => {
        const load = async () => {
            try {
                setLoading(true)
                setError('')
                setReportOverallScore(null)
                const latestEndpoint = `${BACKEND_API_BASE}/api/growth-report/latest`
                const loadImmediateScore = async (endpoint: string): Promise<number | null> => {
                    try {
                        const scoreRes = await fetch(endpoint, { cache: 'no-store' })
                        let scoreData: ImmediateReportApiResult | null = null
                        try {
                            scoreData = await scoreRes.json()
                        } catch {
                            scoreData = null
                        }
                        if (!scoreRes.ok || !scoreData?.success) {
                            return null
                        }
                        return resolveImmediateReportOverallScore(scoreData)
                    } catch {
                        return null
                    }
                }

                if (interviewId) {
                    const interviewEndpoint = `${BACKEND_API_BASE}/api/growth-report/interview/${encodeURIComponent(interviewId)}`
                    const interviewRes = await fetch(interviewEndpoint, { cache: 'no-store' })
                    let interviewData: ApiResult | null = null
                    try {
                        interviewData = await interviewRes.json()
                    } catch {
                        interviewData = null
                    }

                    if (interviewRes.ok && interviewData?.success) {
                        const immediateEndpoint = `${BACKEND_API_BASE}/api/report/interview/${encodeURIComponent(interviewId)}`
                        const immediateScore = await loadImmediateScore(immediateEndpoint)
                        setReportOverallScore(immediateScore)
                        const baseReport = interviewData.report
                        if (baseReport && immediateScore != null) {
                            setReport({
                                ...baseReport,
                                summary: {
                                    ...baseReport.summary,
                                    overall_score: immediateScore,
                                },
                            })
                        } else {
                            setReport(baseReport)
                        }
                        return
                    }
                    throw new Error(interviewData?.error || interviewData?.message || '未找到指定会话复盘')
                }

                const res = await fetch(latestEndpoint, { cache: 'no-store' })
                const data: ApiResult = await res.json()
                if (!res.ok || !data.success) {
                    throw new Error(data.error || '加载复盘失败')
                }
                const immediateScore = await loadImmediateScore(`${BACKEND_API_BASE}/api/report/latest`)
                setReportOverallScore(immediateScore)
                const baseReport = data.report
                if (baseReport && immediateScore != null) {
                    setReport({
                        ...baseReport,
                        summary: {
                            ...baseReport.summary,
                            overall_score: immediateScore,
                        },
                    })
                } else {
                    setReport(baseReport)
                }
            } catch (e) {
                setError(e instanceof Error ? e.message : '加载复盘失败')
            } finally {
                setLoading(false)
            }
        }

        load()
    }, [interviewId])

    const topActions = useMemo(() => {
        if (!report) return []
        return report.improvement_plan.slice(0, 3)
    }, [report])

    const checklistItems = useMemo(() => {
        if (!report) return []
        const scoreText = reportOverallScore == null ? '--' : reportOverallScore.toFixed(1)
        const dominantRound = roundNameMap[report.summary.dominant_round] || report.summary.dominant_round || '未分类'
        return [
            {
                title: '确认本场关键结果',
                detail: `总分 ${scoreText}，主轮次 ${dominantRound}，时长 ${formatDuration(report.summary.duration_seconds)}。`,
                done: reportOverallScore != null && reportOverallScore > 0,
            },
            {
                title: '提炼 1-3 个亮点',
                detail: report.strengths.length
                    ? `已识别 ${Math.min(report.strengths.length, 3)} 个亮点，可用于下次回答模板复用。`
                    : '当前亮点文本不足，建议回放本场高质量回答片段。',
                done: report.strengths.length > 0,
            },
            {
                title: '锁定优先改进项',
                detail: report.weaknesses.length
                    ? `已识别 ${Math.min(report.weaknesses.length, 3)} 个短板，优先处理前两项。`
                    : '短板文本不足，建议从“表达清晰度”和“岗位匹配度”两项先排查。',
                done: report.weaknesses.length > 0,
            },
            {
                title: '制定下一次训练动作',
                detail: topActions.length
                    ? `已生成 ${topActions.length} 条行动建议，建议在 24 小时内完成第一条。`
                    : '建议新增一条“24 小时内完成 1 次同岗位练习”的执行计划。',
                done: topActions.length > 0,
            },
        ]
    }, [report, reportOverallScore, topActions])

    if (loading) {
        return (
            <div className="flex min-h-screen">
                <PersistentSidebar />
                <main className="flex-1 overflow-y-auto">
                    <div className="flex min-h-full items-center justify-center px-4">
                        <div className="rounded-2xl border border-[#E5E5E5] bg-white px-8 py-10 text-center shadow-sm">
                            <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-[#111111] border-t-transparent" />
                            <p className="text-sm font-medium text-[#666666]">正在生成单场复盘...</p>
                        </div>
                    </div>
                </main>
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex min-h-screen">
                <PersistentSidebar />
                <main className="flex-1 overflow-y-auto">
                    <div className="mx-auto max-w-4xl px-6 py-8">
                        <section className="rounded-2xl border border-red-300/60 bg-red-50/70 p-6 shadow-sm">
                            <p className="text-lg font-bold text-red-700">复盘加载失败</p>
                            <p className="mt-2 text-sm text-red-700/90">{error}</p>
                            <div className="mt-4 flex flex-wrap gap-3">
                                {interviewId ? (
                                    <Link href="/review" className="inline-flex items-center gap-2 rounded-lg bg-[#111111] px-4 py-2 text-sm font-semibold text-white hover:bg-[#222222]">
                                        查看最近一场复盘
                                        <ArrowRight className="h-4 w-4" />
                                    </Link>
                                ) : null}
                                <Link href="/history" className="inline-flex items-center gap-2 rounded-lg border border-[#E5E5E5] bg-white px-4 py-2 text-sm font-semibold text-[#111111] hover:bg-[#F5F5F5]">
                                    返回历史记录
                                </Link>
                                <Link href="/interview/setup" className="inline-flex items-center gap-2 rounded-lg border border-[#E5E5E5] bg-white px-4 py-2 text-sm font-semibold text-[#111111] hover:bg-[#F5F5F5]">
                                    重新开始面试
                                </Link>
                            </div>
                        </section>
                    </div>
                </main>
            </div>
        )
    }

    if (!report) {
        return (
            <div className="flex min-h-screen">
                <PersistentSidebar />
                <main className="flex-1 overflow-y-auto">
                    <div className="mx-auto max-w-4xl px-6 py-8">
                        <section className="rounded-2xl border border-[#E5E5E5] bg-white p-8 text-center shadow-sm">
                            <FileText className="mx-auto h-12 w-12 text-[#999999]" />
                            <h1 className="mt-4 text-2xl font-semibold tracking-tight text-[#111111]">暂无可复盘的会话</h1>
                            <p className="mt-2 text-sm text-[#666666]">完成一场面试后，这里会自动生成本场摘要与行动建议。</p>
                            <Link href="/interview/setup" className="mt-6 inline-flex items-center gap-2 rounded-lg bg-[#111111] px-5 py-3 text-sm font-semibold text-white hover:bg-[#222222]">
                                前往开始面试
                                <ArrowRight className="h-4 w-4" />
                            </Link>
                        </section>
                    </div>
                </main>
            </div>
        )
    }

    return (
        <div className="flex min-h-screen">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-6xl px-6 py-8 space-y-6">
                    <section className="rounded-3xl border border-[#E5E5E5] bg-[#FAF9F6] p-6 shadow-sm sm:p-8">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-[#999999]">单场复盘</p>
                <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#111111] sm:text-4xl">先看结论，再进入完整报告</h1>
                <p className="mt-2 text-sm text-[#666666]">你可以先用本页快速定位“下一次训练该做什么”，再进入完整分析页查看证据细节。</p>
                {interviewId && (
                    <p className="mt-2 text-xs font-medium text-[#666666]">当前会话：{interviewId}</p>
                )}

                <div className="mt-6 grid gap-4 sm:grid-cols-3">
                    <StatCard title="综合得分" value={report.summary.overall_score == null ? '--' : report.summary.overall_score.toFixed(1)} icon={Radar} />
                    <StatCard title="主面试轮次" value={roundNameMap[report.summary.dominant_round] || report.summary.dominant_round} icon={FileText} />
                    <StatCard title="会话时长" value={formatDuration(report.summary.duration_seconds)} icon={Clock3} />
                </div>
            </section>

            <section className="mt-6 rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-[#2E6A45]" />
                    <h2 className="text-xl font-semibold text-[#111111]">面试后回顾清单</h2>
                </div>
                <p className="mt-2 text-sm text-[#666666]">每场结束后按此清单快速复盘，确保结论可执行、可追踪。</p>

                <div className="mt-4 space-y-3">
                    {checklistItems.map((item, index) => (
                        <article key={item.title} className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <p className="text-sm font-semibold text-[#111111]">{index + 1}. {item.title}</p>
                                    <p className="mt-1 text-sm leading-6 text-[#666666]">{item.detail}</p>
                                </div>
                                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${item.done ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                                    {item.done ? '已生成' : '待补充'}
                                </span>
                            </div>
                        </article>
                    ))}
                </div>
            </section>

            <section className="mt-6 grid gap-4 lg:grid-cols-2">
                <article className="rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                    <div className="mb-3 flex items-center gap-2">
                        <CheckCircle className="h-5 w-5 text-emerald-600" />
                        <h2 className="text-xl font-semibold text-[#111111]">本场亮点</h2>
                    </div>
                    <ul className="space-y-2 text-sm text-[#333333]">
                        {(report.strengths.length ? report.strengths : ['本场暂无明确亮点文本。']).slice(0, 3).map((item, index) => (
                            <li key={index} className="rounded-lg border border-emerald-200/70 bg-emerald-50/70 p-3">{item}</li>
                        ))}
                    </ul>
                </article>

                <article className="rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                    <div className="mb-3 flex items-center gap-2">
                        <AlertTriangle className="h-5 w-5 text-amber-600" />
                        <h2 className="text-xl font-semibold text-[#111111]">优先改进点</h2>
                    </div>
                    <ul className="space-y-2 text-sm text-[#333333]">
                        {(report.weaknesses.length ? report.weaknesses : ['本场暂无明确短板文本。']).slice(0, 3).map((item, index) => (
                            <li key={index} className="rounded-lg border border-amber-200/70 bg-amber-50/70 p-3">{item}</li>
                        ))}
                    </ul>
                </article>
            </section>

            <section className="mt-6 rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                <h2 className="text-xl font-semibold text-[#111111]">下一步动作</h2>
                <div className="mt-4 grid gap-3 lg:grid-cols-3">
                    {(topActions.length ? topActions : [{ focus: '继续练习', action: '完成下一场岗位化面试，积累更多样本。', target: '24小时内完成1次' }]).map((item, index) => (
                        <article key={index} className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
                            <p className="text-sm font-semibold text-[#111111]">{item.focus}</p>
                            <p className="mt-2 text-sm text-[#666666]">{item.action}</p>
                            <p className="mt-2 text-xs font-medium text-[#666666]">目标：{item.target}</p>
                        </article>
                    ))}
                </div>

                <div className="mt-6 flex flex-wrap items-center gap-3">
                    <Link href={interviewId ? `/report?interviewId=${encodeURIComponent(interviewId)}` : '/report'} className="inline-flex items-center gap-2 rounded-lg bg-[#111111] px-4 py-2 text-sm font-semibold text-white hover:bg-[#222222]">
                        查看完整成长报告
                        <ArrowRight className="h-4 w-4" />
                    </Link>
                    <Link href="/interview/setup" className="inline-flex items-center gap-2 rounded-lg border border-[#E5E5E5] bg-white px-4 py-2 text-sm font-semibold text-[#111111] hover:bg-[#F5F5F5]">
                        再来一场面试
                    </Link>
                    <Link href="/history" className="inline-flex items-center gap-2 rounded-lg border border-[#E5E5E5] bg-white px-4 py-2 text-sm font-semibold text-[#111111] hover:bg-[#F5F5F5]">
                        查看历史记录
                    </Link>
                </div>
            </section>
        </div>
    </main>
</div>
    )
}

function ReviewPageFallback() {
    return (
        <div className="flex min-h-screen">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="flex min-h-full items-center justify-center px-4">
                    <div className="rounded-2xl border border-[#E5E5E5] bg-white px-8 py-10 text-center shadow-sm">
                        <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-[#111111] border-t-transparent" />
                        <p className="text-sm font-medium text-[#666666]">正在生成单场复盘...</p>
                    </div>
                </div>
            </main>
        </div>
    )
}

export default function ReviewPage() {
    return (
        <Suspense fallback={<ReviewPageFallback />}>
            <ReviewPageContent />
        </Suspense>
    )
}

function StatCard({
    title,
    value,
    icon: Icon,
}: {
    title: string
    value: string
    icon: LucideIcon
}) {
    return (
        <article className="rounded-2xl border border-[#E5E5E5] bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2">
                <Icon className="h-4 w-4 text-[#666666]" />
                <p className="text-xs font-medium uppercase tracking-[0.12em] text-[#999999]">{title}</p>
            </div>
            <p className="mt-2 text-2xl font-semibold text-[#111111]">{value}</p>
        </article>
    )
}


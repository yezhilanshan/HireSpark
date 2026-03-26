'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
    AlertCircle,
    CheckCircle,
    FileText,
    Home,
    Clock,
    TrendingUp
} from 'lucide-react'

const BACKEND_API_BASE = (process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000').replace(/\/$/, '')

type ScoreBreakdown = {
    technical_correctness: number
    knowledge_depth: number
    logical_rigor: number
    expression_clarity: number
    job_match: number
    adaptability: number
}

type ImprovementItem = {
    focus: string
    action: string
    target: string
}

type FollowupItem = {
    round: string
    question: string
    answer: string
    feedback: string
}

type GrowthReport = {
    summary: {
        overall_score: number
        interview_count: number
        started_at: string
        ended_at: string
        duration_seconds: number
        dominant_round: string
    }
    score_breakdown: ScoreBreakdown
    strengths: string[]
    weaknesses: string[]
    improvement_plan: ImprovementItem[]
    followup_chain: FollowupItem[]
}

type TrendPoint = {
    label: string
    overall_score: number
}

type ApiResult = {
    success: boolean
    report: GrowthReport | null
    trend: TrendPoint[]
    message?: string
    error?: string
}

const roundNameMap: Record<string, string> = {
    technical: '技术基础面',
    project: '项目深度面',
    system_design: '系统设计面',
    hr: 'HR综合面'
}

const scoreItems: Array<{ key: keyof ScoreBreakdown; label: string; weight: string; color: string }> = [
    { key: 'technical_correctness', label: '技术正确性', weight: '30%', color: 'bg-blue-500' },
    { key: 'knowledge_depth', label: '知识深度', weight: '15%', color: 'bg-violet-500' },
    { key: 'logical_rigor', label: '逻辑严谨性', weight: '15%', color: 'bg-cyan-500' },
    { key: 'expression_clarity', label: '表达清晰度', weight: '15%', color: 'bg-emerald-500' },
    { key: 'job_match', label: '岗位匹配度', weight: '15%', color: 'bg-amber-500' },
    { key: 'adaptability', label: '应变能力', weight: '10%', color: 'bg-rose-500' }
]

function formatDuration(seconds: number): string {
    const safe = Math.max(0, Number.isFinite(seconds) ? Math.floor(seconds) : 0)
    const min = Math.floor(safe / 60)
    const sec = safe % 60
    if (min <= 0) return `${sec}秒`
    return `${min}分${sec}秒`
}

function scoreLevel(score: number): 'A' | 'B' | 'C' {
    if (score >= 80) return 'A'
    if (score >= 65) return 'B'
    return 'C'
}

export default function ReportPage() {
    const router = useRouter()
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [report, setReport] = useState<GrowthReport | null>(null)
    const [trend, setTrend] = useState<TrendPoint[]>([])

    useEffect(() => {
        const load = async () => {
            try {
                const res = await fetch(`${BACKEND_API_BASE}/api/growth-report/latest`)
                const data: ApiResult = await res.json()
                if (!res.ok || !data.success) {
                    throw new Error(data.error || '加载成长报告失败')
                }
                setReport(data.report)
                setTrend(data.trend || [])
            } catch (e) {
                setError(e instanceof Error ? e.message : '加载成长报告失败')
            } finally {
                setLoading(false)
            }
        }

        load()
    }, [])

    const overallLevel = useMemo(() => {
        const score = report?.summary?.overall_score || 0
        return scoreLevel(score)
    }, [report])

    if (loading) {
        return (
            <div className='min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center'>
                <div className='text-center'>
                    <div className='animate-spin rounded-full h-16 w-16 border-b-2 border-indigo-600 mx-auto mb-4'></div>
                    <p className='text-gray-600 dark:text-gray-300'>正在生成成长报告...</p>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className='min-h-screen bg-gray-50 dark:bg-gray-900 p-4'>
                <div className='max-w-5xl mx-auto bg-white dark:bg-gray-800 rounded-2xl shadow p-8'>
                    <p className='text-red-600 dark:text-red-400 font-semibold mb-4'>{error}</p>
                    <button
                        onClick={() => router.push('/')}
                        className='inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-white font-semibold hover:bg-indigo-700 transition'
                    >
                        <Home className='w-4 h-4' />
                        返回首页
                    </button>
                </div>
            </div>
        )
    }

    if (!report) {
        return (
            <div className='min-h-screen bg-gray-50 dark:bg-gray-900 p-4'>
                <div className='max-w-5xl mx-auto bg-white dark:bg-gray-800 rounded-2xl shadow p-10 text-center'>
                    <FileText className='w-14 h-14 mx-auto mb-4 text-indigo-500' />
                    <h2 className='text-2xl font-bold text-gray-800 dark:text-gray-100 mb-2'>暂无成长报告</h2>
                    <p className='text-gray-600 dark:text-gray-300 mb-6'>请先完成一次多轮面试，对话过程会自动生成成长分析。</p>
                    <button
                        onClick={() => router.push('/interview-setup')}
                        className='inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-3 text-white font-semibold hover:bg-indigo-700 transition'
                    >
                        <Clock className='w-4 h-4' />
                        开始模拟面试
                    </button>
                </div>
            </div>
        )
    }

    return (
        <div className='min-h-screen bg-gray-50 dark:bg-gray-900 p-4 transition-colors'>
            <div className='max-w-7xl mx-auto space-y-6'>
                <div className='bg-white dark:bg-gray-800 rounded-2xl shadow-md p-6'>
                    <div className='flex flex-wrap items-start justify-between gap-4'>
                        <div className='flex items-start gap-3'>
                            <FileText className='w-8 h-8 text-indigo-600 dark:text-indigo-400 mt-1' />
                            <div>
                                <h1 className='text-3xl font-bold text-gray-900 dark:text-gray-100'>AI 面试成长报告</h1>
                                <p className='text-gray-600 dark:text-gray-300 mt-1'>基于本轮面试过程问答与追问链路，自动总结你的表现与提升方向。</p>
                            </div>
                        </div>
                        <button
                            onClick={() => router.push('/')}
                            className='inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-white font-semibold hover:bg-indigo-700 transition'
                        >
                            <Home className='w-4 h-4' />
                            首页
                        </button>
                    </div>
                </div>

                <div className='grid lg:grid-cols-4 gap-4'>
                    <div className='bg-gradient-to-br from-indigo-50 to-indigo-100 dark:from-indigo-900/30 dark:to-indigo-800/30 rounded-2xl p-5'>
                        <p className='text-sm text-indigo-700 dark:text-indigo-300 font-semibold'>综合得分</p>
                        <p className='text-4xl font-black text-indigo-900 dark:text-indigo-100 mt-2'>{report.summary.overall_score.toFixed(1)}</p>
                        <p className='mt-2 text-xs text-indigo-700 dark:text-indigo-300'>评级 {overallLevel}</p>
                    </div>
                    <div className='bg-gradient-to-br from-cyan-50 to-cyan-100 dark:from-cyan-900/30 dark:to-cyan-800/30 rounded-2xl p-5'>
                        <p className='text-sm text-cyan-700 dark:text-cyan-300 font-semibold'>主面试轮次</p>
                        <p className='text-2xl font-black text-cyan-900 dark:text-cyan-100 mt-2'>{roundNameMap[report.summary.dominant_round] || report.summary.dominant_round}</p>
                    </div>
                    <div className='bg-gradient-to-br from-emerald-50 to-emerald-100 dark:from-emerald-900/30 dark:to-emerald-800/30 rounded-2xl p-5'>
                        <p className='text-sm text-emerald-700 dark:text-emerald-300 font-semibold'>有效问答轮次</p>
                        <p className='text-3xl font-black text-emerald-900 dark:text-emerald-100 mt-2'>{report.summary.interview_count}</p>
                    </div>
                    <div className='bg-gradient-to-br from-amber-50 to-amber-100 dark:from-amber-900/30 dark:to-amber-800/30 rounded-2xl p-5'>
                        <p className='text-sm text-amber-700 dark:text-amber-300 font-semibold'>面试时长</p>
                        <p className='text-3xl font-black text-amber-900 dark:text-amber-100 mt-2'>{formatDuration(report.summary.duration_seconds)}</p>
                    </div>
                </div>

                <div className='grid lg:grid-cols-5 gap-6'>
                    <div className='lg:col-span-3 bg-white dark:bg-gray-800 rounded-2xl shadow-md p-6'>
                        <div className='flex items-center gap-2 mb-5'>
                            <FileText className='w-5 h-5 text-indigo-500' />
                            <h2 className='text-2xl font-bold text-gray-900 dark:text-gray-100'>多维能力评分</h2>
                        </div>
                        <div className='space-y-4'>
                            {scoreItems.map((item) => {
                                const value = report.score_breakdown[item.key]
                                return (
                                    <div key={item.key}>
                                        <div className='flex items-center justify-between mb-1'>
                                            <p className='text-sm font-semibold text-gray-700 dark:text-gray-200'>
                                                {item.label} <span className='text-xs text-gray-500 dark:text-gray-400'>({item.weight})</span>
                                            </p>
                                            <p className='text-sm font-bold text-gray-900 dark:text-gray-100'>{value.toFixed(1)}</p>
                                        </div>
                                        <div className='h-2.5 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden'>
                                            <div className={`h-full ${item.color}`} style={{ width: `${Math.max(3, value)}%` }}></div>
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    </div>

                    <div className='lg:col-span-2 space-y-6'>
                        <div className='bg-white dark:bg-gray-800 rounded-2xl shadow-md p-6'>
                            <div className='flex items-center gap-2 mb-4'>
                                <CheckCircle className='w-5 h-5 text-emerald-500' />
                                <h3 className='text-xl font-bold text-gray-900 dark:text-gray-100'>亮点</h3>
                            </div>
                            <ul className='space-y-3'>
                                {report.strengths.map((text, idx) => (
                                    <li key={idx} className='text-sm text-gray-700 dark:text-gray-300 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg p-3'>
                                        {text}
                                    </li>
                                ))}
                            </ul>
                        </div>

                        <div className='bg-white dark:bg-gray-800 rounded-2xl shadow-md p-6'>
                            <div className='flex items-center gap-2 mb-4'>
                                <AlertCircle className='w-5 h-5 text-orange-500' />
                                <h3 className='text-xl font-bold text-gray-900 dark:text-gray-100'>待提升</h3>
                            </div>
                            <ul className='space-y-3'>
                                {report.weaknesses.map((text, idx) => (
                                    <li key={idx} className='text-sm text-gray-700 dark:text-gray-300 bg-orange-50 dark:bg-orange-900/20 rounded-lg p-3'>
                                        {text}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </div>
                </div>

                <div className='grid lg:grid-cols-2 gap-6'>
                    <div className='bg-white dark:bg-gray-800 rounded-2xl shadow-md p-6'>
                        <div className='flex items-center gap-2 mb-5'>
                            <AlertCircle className='w-5 h-5 text-violet-500' />
                            <h2 className='text-2xl font-bold text-gray-900 dark:text-gray-100'>追问链路</h2>
                        </div>
                        <div className='space-y-4 max-h-[460px] overflow-y-auto pr-1'>
                            {report.followup_chain.map((item, idx) => (
                                <div key={idx} className='rounded-xl border border-gray-200 dark:border-gray-700 p-4'>
                                    <p className='text-xs text-violet-600 dark:text-violet-300 font-semibold mb-2'>
                                        第 {idx + 1} 轮 · {roundNameMap[item.round] || item.round}
                                    </p>
                                    <p className='text-sm text-gray-900 dark:text-gray-100 font-medium mb-2'>问：{item.question || '（无问题文本）'}</p>
                                    <p className='text-sm text-gray-700 dark:text-gray-300 mb-2'>答：{item.answer || '（无回答文本）'}</p>
                                    <p className='text-xs text-gray-500 dark:text-gray-400'>反馈：{item.feedback || '（无反馈文本）'}</p>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className='space-y-6'>
                        <div className='bg-white dark:bg-gray-800 rounded-2xl shadow-md p-6'>
                            <div className='flex items-center gap-2 mb-5'>
                                <FileText className='w-5 h-5 text-indigo-500' />
                                <h2 className='text-2xl font-bold text-gray-900 dark:text-gray-100'>个性化提升计划</h2>
                            </div>
                            <div className='space-y-4'>
                                {report.improvement_plan.map((item, idx) => (
                                    <div key={idx} className='rounded-xl bg-indigo-50 dark:bg-indigo-900/20 p-4'>
                                        <p className='text-sm font-bold text-indigo-900 dark:text-indigo-200 mb-1'>{item.focus}</p>
                                        <p className='text-sm text-gray-700 dark:text-gray-300 mb-2'>{item.action}</p>
                                        <p className='text-xs text-indigo-700 dark:text-indigo-300'>目标：{item.target}</p>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className='bg-white dark:bg-gray-800 rounded-2xl shadow-md p-6'>
                            <div className='flex items-center gap-2 mb-5'>
                                <TrendingUp className='w-5 h-5 text-emerald-500' />
                                <h2 className='text-2xl font-bold text-gray-900 dark:text-gray-100'>成长趋势</h2>
                            </div>
                            <div className='space-y-3'>
                                {trend.length === 0 ? (
                                    <p className='text-sm text-gray-500 dark:text-gray-400'>历史样本不足，完成更多面试后可查看趋势。</p>
                                ) : (
                                    trend.map((point) => (
                                        <div key={point.label}>
                                            <div className='flex items-center justify-between mb-1'>
                                                <p className='text-sm font-medium text-gray-700 dark:text-gray-300'>{point.label}</p>
                                                <p className='text-sm font-bold text-gray-900 dark:text-gray-100'>{point.overall_score.toFixed(1)}</p>
                                            </div>
                                            <div className='h-2.5 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden'>
                                                <div className='h-full bg-emerald-500' style={{ width: `${Math.max(3, point.overall_score)}%` }}></div>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { AlertCircle, ArrowLeft, ArrowRight, FileText, LineChart, Mic2, Sparkles, Target, TrendingUp } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const BACKEND_API_BASE = (process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000').replace(/\/$/, '')

type Dimension = { key: string; label: string; score: number; source?: string }
type ReviewDimension = {
    label?: string
    key?: string
    score?: number
    final_score?: number
    text_base_score?: number
    speech_adjustment?: number
    speech_used?: boolean
}
type Review = {
    turn_id?: string
    round_type?: string
    question?: string
    answer?: string
    rubric_level?: string
    overall_score?: number
    overall_score_base?: number
    overall_score_final?: number
    speech_used?: boolean
    speech_expression_score?: number | null
    dimensions?: ReviewDimension[]
    summary?: { strengths?: string[]; weaknesses?: string[]; next_actions?: string[] }
}
type Report = {
    meta?: { report_mode?: string; has_structured_evaluations?: boolean }
    summary: { overall_score: number; level?: string; interview_count?: number; duration_seconds?: number; dominant_round?: string }
    dimensions?: Dimension[]
    round_breakdown?: Array<{ round_type: string; count: number; avg_score: number }>
    expression?: { available?: boolean; dimensions?: Record<string, number>; summary?: Record<string, number> }
    coaching?: { strengths?: string[]; weaknesses?: string[]; next_actions?: string[] }
    question_reviews?: Review[]
    score_breakdown?: Record<string, number>
    expression_detail?: { available?: boolean; dimensions?: Record<string, number>; summary?: Record<string, number> }
    strengths?: string[]
    weaknesses?: string[]
    improvement_plan?: Array<{ action?: string; focus?: string }>
}
type TrendPoint = { label: string; overall_score: number }
type History = {
    session_count: number
    average_score: number
    best_score: number
    latest_score: number
    delta_from_previous: number | null
    trend: TrendPoint[]
    sessions: Array<{ session_index: number; summary?: Report['summary']; started_at?: string }>
}
type ApiResult = { success: boolean; report: Report | null; latest_report?: Report | null; trend: TrendPoint[]; history?: History; error?: string; message?: string }

const roundNameMap: Record<string, string> = {
    technical: '技术面',
    project: '项目面',
    system_design: '系统设计',
    hr: 'HR 面',
}

const legacyLabels: Record<string, string> = {
    technical_correctness: '技术准确性',
    knowledge_depth: '知识深度',
    logical_rigor: '逻辑严谨性',
    expression_clarity: '表达清晰度',
    job_match: '岗位匹配度',
    adaptability: '应变与稳定性',
}

function formatDuration(seconds = 0) {
    const safe = Math.max(0, Math.floor(seconds))
    const min = Math.floor(safe / 60)
    const sec = safe % 60
    return min > 0 ? `${min}分${sec}秒` : `${sec}秒`
}

function scoreTone(score: number) {
    if (score >= 85) return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200'
    if (score >= 70) return 'bg-cyan-100 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-200'
    if (score >= 55) return 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-200'
    return 'bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-200'
}

function cardClass(extra = '') {
    return `rounded-3xl border border-white/70 bg-white/85 shadow-xl backdrop-blur dark:border-slate-700 dark:bg-slate-900/70 ${extra}`.trim()
}

function getSpeechImpactedDimensions(review: Review) {
    return (review.dimensions || []).filter(item => Math.abs(Number(item.speech_adjustment || 0)) >= 0.1)
}

function normalizeReport(report: Report | null) {
    if (!report) return null
    const dimensions = (report.dimensions && report.dimensions.length > 0)
        ? report.dimensions
        : Object.entries(report.score_breakdown || {}).map(([key, score]) => ({
            key,
            label: legacyLabels[key] || key,
            score: Number(score || 0),
            source: 'legacy',
        }))
    const coaching = report.coaching || {
        strengths: report.strengths || [],
        weaknesses: report.weaknesses || [],
        next_actions: (report.improvement_plan || []).map(item => item.action || item.focus || '').filter(Boolean),
    }
    const expression = report.expression || report.expression_detail || {}
    return { report, dimensions, coaching, expression, reviews: report.question_reviews || [], score: Number(report.summary?.overall_score || 0) }
}

export default function ReportPage() {
    const router = useRouter()
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [payload, setPayload] = useState<ApiResult | null>(null)

    useEffect(() => {
        const load = async () => {
            try {
                const res = await fetch(`${BACKEND_API_BASE}/api/growth-report/latest`, { cache: 'no-store' })
                const data: ApiResult = await res.json()
                if (!res.ok || !data.success) throw new Error(data.error || data.message || '获取成长报告失败')
                setPayload(data)
            } catch (e) {
                setError(e instanceof Error ? e.message : '获取成长报告失败')
            } finally {
                setLoading(false)
            }
        }
        load()
    }, [])

    const latest = useMemo(() => normalizeReport(payload?.latest_report || payload?.report || null), [payload])
    const history = payload?.history
    const trend = history?.trend || payload?.trend || []
    const radarData = (latest?.dimensions || []).slice(0, 6).map(item => ({ subject: item.label, score: Math.round(item.score) }))

    if (loading) return <main className='relative min-h-screen p-4 sm:p-8'><div className='mx-auto max-w-6xl'><div className={cardClass('p-10 text-center')}>报告加载中...</div></div></main>
    if (error) return <main className='relative min-h-screen p-4 sm:p-8'><div className='mx-auto max-w-3xl'><div className={cardClass('p-8')}><div className='flex items-center gap-3 text-rose-600 dark:text-rose-300'><AlertCircle className='h-5 w-5' />报告加载失败</div><p className='mt-4 text-sm text-slate-600 dark:text-slate-300'>{error}</p></div></div></main>
    if (!latest) return <main className='relative min-h-screen p-4 sm:p-8'><div className='mx-auto max-w-3xl'><div className={cardClass('p-10 text-center')}><FileText className='mx-auto h-12 w-12 text-cyan-600 dark:text-cyan-300' /><p className='mt-4 text-lg font-semibold text-slate-900 dark:text-slate-100'>暂无成长报告</p></div></div></main>

    return (
        <main className='relative min-h-screen overflow-hidden p-4 sm:p-8'>
            <div className='pointer-events-none absolute inset-0'>
                <div className='absolute -left-20 top-10 h-56 w-56 rounded-full bg-cyan-400/20 blur-3xl dark:bg-cyan-500/10' />
                <div className='absolute right-4 top-24 h-64 w-64 rounded-full bg-orange-300/20 blur-3xl dark:bg-orange-500/10' />
                <div className='absolute bottom-10 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-emerald-400/15 blur-3xl dark:bg-emerald-500/10' />
            </div>

            <div className='relative mx-auto max-w-7xl space-y-6'>
                <section className={cardClass('p-6 sm:p-8')}>
                    <div className='mb-8 flex flex-wrap items-center justify-between gap-4'>
                        <div className='inline-flex items-center gap-2 rounded-full border border-cyan-700/20 bg-cyan-50/80 px-4 py-2 text-sm font-semibold text-cyan-800 dark:border-cyan-300/30 dark:bg-cyan-900/20 dark:text-cyan-200'>
                            <Sparkles className='h-4 w-4' /> AI 面试成长报告
                        </div>
                        <div className='flex flex-wrap gap-3'>
                            <button onClick={() => router.push('/')} className='inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white/80 px-4 py-2.5 text-sm font-semibold text-slate-700 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-200'><ArrowLeft className='h-4 w-4' />返回首页</button>
                            <button onClick={() => router.push('/interview-setup')} className='inline-flex items-center gap-2 rounded-xl bg-cyan-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-800'><ArrowRight className='h-4 w-4' />再来一次面试</button>
                        </div>
                    </div>

                    <div className='grid gap-6 lg:grid-cols-[1.3fr_1fr]'>
                        <div>
                            <h1 className='text-4xl font-black leading-tight text-slate-900 dark:text-slate-100 sm:text-5xl'>最近一场复盘<span className='block bg-gradient-to-r from-cyan-600 to-orange-500 bg-clip-text text-transparent'>历史多场趋势</span></h1>
                            <p className='mt-5 max-w-2xl text-base leading-relaxed text-slate-600 dark:text-slate-300'>现在这份报告分成两层：最近一场详细复盘，以及跨多场面试的历史趋势。</p>
                            <div className='mt-8 flex flex-wrap items-end gap-4'>
                                <div>
                                    <p className='text-sm text-slate-500 dark:text-slate-400'>最近一场总分</p>
                                    <p className='mt-2 text-6xl font-black text-slate-900 dark:text-slate-100'>{latest.score.toFixed(1)}</p>
                                </div>
                                <span className={`rounded-full px-4 py-2 text-sm font-semibold ${scoreTone(latest.score)}`}>{payload?.report?.summary?.level || 'latest'}</span>
                            </div>
                        </div>
                        <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-1'>
                            <div className='rounded-2xl border border-cyan-200/60 bg-white/70 p-5 shadow-lg dark:border-cyan-900/60 dark:bg-slate-900/60'>
                                <p className='text-sm text-cyan-700 dark:text-cyan-300'>最近一场重点轮次</p>
                                <p className='mt-3 text-2xl font-bold text-slate-900 dark:text-slate-100'>{roundNameMap[latest.report.summary?.dominant_round || ''] || latest.report.summary?.dominant_round || '未分类'}</p>
                                <p className='mt-2 text-sm text-slate-500 dark:text-slate-400'>时长 {formatDuration(latest.report.summary?.duration_seconds || 0)}，题目 {latest.report.summary?.interview_count || 0} 道</p>
                            </div>
                            <div className='rounded-2xl border border-orange-200/60 bg-white/70 p-5 shadow-lg dark:border-orange-900/60 dark:bg-slate-900/60'>
                                <p className='text-sm text-orange-700 dark:text-orange-300'>历史表现概览</p>
                                <div className='mt-3 grid grid-cols-3 gap-3 text-sm'>
                                    <div><p className='text-slate-500 dark:text-slate-400'>场次</p><p className='mt-1 text-xl font-bold text-slate-900 dark:text-slate-100'>{history?.session_count ?? 0}</p></div>
                                    <div><p className='text-slate-500 dark:text-slate-400'>均分</p><p className='mt-1 text-xl font-bold text-slate-900 dark:text-slate-100'>{(history?.average_score ?? latest.score).toFixed(1)}</p></div>
                                    <div><p className='text-slate-500 dark:text-slate-400'>最高</p><p className='mt-1 text-xl font-bold text-slate-900 dark:text-slate-100'>{(history?.best_score ?? latest.score).toFixed(1)}</p></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                <section className='grid gap-6 xl:grid-cols-[1.05fr_0.95fr]'>
                    <div className={cardClass('p-6')}>
                        <div className='mb-5 flex items-start gap-3'><div className='rounded-2xl border border-cyan-200 bg-cyan-50 p-2 text-cyan-700 dark:border-cyan-500/20 dark:bg-cyan-500/10 dark:text-cyan-200'><Target className='h-5 w-5' /></div><div><h2 className='text-xl font-bold text-slate-900 dark:text-slate-100'>最近一场能力总览</h2><p className='mt-1 text-sm text-slate-500 dark:text-slate-400'>优先使用结构化评价，没有结构化结果时回退到兼容维度。</p></div></div>
                        <div className='grid gap-6 lg:grid-cols-[0.95fr_1.05fr]'>
                            <div className='h-[320px] rounded-[24px] border border-slate-200 bg-white/70 p-3 dark:border-slate-700 dark:bg-slate-950/40'>
                                <ResponsiveContainer width='100%' height='100%'>
                                    <RadarChart data={radarData}>
                                        <PolarGrid stroke='rgba(148,163,184,0.22)' />
                                        <PolarAngleAxis dataKey='subject' tick={{ fill: '#64748b', fontSize: 12 }} />
                                        <PolarRadiusAxis domain={[0, 100]} tickCount={6} axisLine={false} tick={false} />
                                        <Radar dataKey='score' stroke='#0891b2' fill='#06b6d4' fillOpacity={0.22} />
                                        <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.96)', border: '1px solid rgba(148,163,184,0.2)', borderRadius: 16, color: '#0f172a' }} />
                                    </RadarChart>
                                </ResponsiveContainer>
                            </div>
                            <div className='space-y-3'>
                                {latest.dimensions.map(item => (
                                    <div key={item.key} className='rounded-[22px] border border-slate-200 bg-white/70 p-4 dark:border-slate-700 dark:bg-slate-950/40'>
                                        <div className='flex items-center justify-between gap-3'>
                                            <div><p className='text-sm font-semibold text-slate-900 dark:text-slate-100'>{item.label}</p><p className='mt-1 text-xs text-slate-500 dark:text-slate-400'>{item.source === 'evaluation_service' ? '来自结构化评价聚合' : '来自兼容评分映射'}</p></div>
                                            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${scoreTone(item.score)}`}>{item.score.toFixed(1)}</span>
                                        </div>
                                        <div className='mt-3 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800'><div className='h-full rounded-full bg-gradient-to-r from-cyan-500 via-sky-500 to-orange-400' style={{ width: `${Math.max(6, Math.min(100, item.score))}%` }} /></div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className={cardClass('p-6')}>
                        <div className='mb-5 flex items-start gap-3'><div className='rounded-2xl border border-cyan-200 bg-cyan-50 p-2 text-cyan-700 dark:border-cyan-500/20 dark:bg-cyan-500/10 dark:text-cyan-200'><LineChart className='h-5 w-5' /></div><div><h2 className='text-xl font-bold text-slate-900 dark:text-slate-100'>历史多场趋势</h2><p className='mt-1 text-sm text-slate-500 dark:text-slate-400'>这里展示跨多场面试的整体得分变化。</p></div></div>
                        <div className='h-[320px] rounded-[24px] border border-slate-200 bg-white/70 p-3 dark:border-slate-700 dark:bg-slate-950/40'>
                            <ResponsiveContainer width='100%' height='100%'>
                                <AreaChart data={trend}>
                                    <defs><linearGradient id='trendFill' x1='0' y1='0' x2='0' y2='1'><stop offset='0%' stopColor='#06b6d4' stopOpacity={0.32} /><stop offset='100%' stopColor='#06b6d4' stopOpacity={0.04} /></linearGradient></defs>
                                    <CartesianGrid stroke='rgba(148,163,184,0.16)' vertical={false} />
                                    <XAxis dataKey='label' tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} />
                                    <YAxis tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} domain={[0, 100]} />
                                    <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.96)', border: '1px solid rgba(148,163,184,0.2)', borderRadius: 16, color: '#0f172a' }} />
                                    <Area type='monotone' dataKey='overall_score' stroke='#0891b2' strokeWidth={3} fill='url(#trendFill)' />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </section>

                <section className='grid gap-6 lg:grid-cols-[0.95fr_1.05fr]'>
                    <div className={cardClass('p-6')}>
                        <div className='mb-5 flex items-start gap-3'><div className='rounded-2xl border border-cyan-200 bg-cyan-50 p-2 text-cyan-700 dark:border-cyan-500/20 dark:bg-cyan-500/10 dark:text-cyan-200'><Mic2 className='h-5 w-5' /></div><div><h2 className='text-xl font-bold text-slate-900 dark:text-slate-100'>表达与语音分析</h2><p className='mt-1 text-sm text-slate-500 dark:text-slate-400'>这一块展示最近一场面试里的表达类客观指标。</p></div></div>
                        {latest.expression.available ? <div className='grid gap-3 sm:grid-cols-2'>{[['语速评分', Number(latest.expression.dimensions?.speech_rate_score || 0)], ['停顿评分', Number(latest.expression.dimensions?.pause_anomaly_score || 0)], ['口头禅评分', Number(latest.expression.dimensions?.filler_frequency_score || 0)], ['流畅度', Number(latest.expression.dimensions?.fluency_score || 0)], ['清晰度', Number(latest.expression.dimensions?.clarity_score || 0)]].map(([label, value]) => <div key={String(label)} className='rounded-[22px] border border-slate-200 bg-white/70 p-4 dark:border-slate-700 dark:bg-slate-950/40'><p className='text-xs uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400'>{label}</p><p className='mt-3 text-3xl font-bold text-slate-900 dark:text-slate-100'>{Number(value).toFixed(1)}</p></div>)}</div> : <div className='rounded-[24px] border border-dashed border-slate-300 bg-white/60 p-6 text-sm leading-7 text-slate-500 dark:border-slate-700 dark:bg-slate-950/35 dark:text-slate-400'>当前还没有足够的语音样本用于表达分析。</div>}
                    </div>

                    <div className='grid gap-6 md:grid-cols-2'>
                        <div className='rounded-3xl border border-emerald-200 bg-emerald-50/75 p-6 shadow-lg dark:border-emerald-500/20 dark:bg-emerald-500/10'>
                            <h3 className='text-lg font-bold text-emerald-700 dark:text-emerald-200'>做得好的地方</h3>
                            <div className='mt-4 space-y-3'>{(latest.coaching.strengths || []).slice(0, 4).map((text, idx) => <div key={`${text}-${idx}`} className='rounded-2xl border border-emerald-200/80 bg-white/70 p-4 text-sm leading-7 text-slate-700 dark:border-emerald-500/10 dark:bg-black/10 dark:text-emerald-50/90'>{text}</div>)}</div>
                        </div>
                        <div className='rounded-3xl border border-amber-200 bg-amber-50/75 p-6 shadow-lg dark:border-amber-500/20 dark:bg-amber-500/10'>
                            <h3 className='text-lg font-bold text-amber-700 dark:text-amber-200'>仍可提升的地方</h3>
                            <div className='mt-4 space-y-3'>{(latest.coaching.weaknesses || []).slice(0, 4).map((text, idx) => <div key={`${text}-${idx}`} className='rounded-2xl border border-amber-200/80 bg-white/70 p-4 text-sm leading-7 text-slate-700 dark:border-amber-500/10 dark:bg-black/10 dark:text-amber-50/90'>{text}</div>)}</div>
                        </div>
                        <div className='md:col-span-2 rounded-3xl border border-cyan-200 bg-cyan-50/75 p-6 shadow-lg dark:border-cyan-500/20 dark:bg-cyan-500/10'>
                            <div className='mb-4 flex items-center gap-2 text-cyan-700 dark:text-cyan-200'><TrendingUp className='h-5 w-5' /><h3 className='text-lg font-bold'>下一步行动建议</h3></div>
                            <div className='grid gap-3 md:grid-cols-3'>{(latest.coaching.next_actions || []).slice(0, 3).map((text, idx) => <div key={`${text}-${idx}`} className='rounded-[22px] border border-cyan-200/80 bg-white/70 p-4 dark:border-cyan-500/10 dark:bg-black/10'><p className='text-xs uppercase tracking-[0.22em] text-cyan-700 dark:text-cyan-200/70'>Action {idx + 1}</p><p className='mt-3 text-sm leading-7 text-slate-700 dark:text-cyan-50/90'>{text}</p></div>)}</div>
                        </div>
                    </div>
                </section>

                {history?.sessions?.length ? (
                    <section className={cardClass('p-6')}>
                        <div className='mb-5 flex items-start gap-3'>
                            <div className='rounded-2xl border border-cyan-200 bg-cyan-50 p-2 text-cyan-700 dark:border-cyan-500/20 dark:bg-cyan-500/10 dark:text-cyan-200'>
                                <LineChart className='h-5 w-5' />
                            </div>
                            <div>
                                <h2 className='text-xl font-bold text-slate-900 dark:text-slate-100'>历史场次摘要</h2>
                                <p className='mt-1 text-sm text-slate-500 dark:text-slate-400'>用最近几次面试的摘要，快速判断你是在稳定进步还是有波动。</p>
                            </div>
                        </div>
                        <div className='grid gap-4 md:grid-cols-2 xl:grid-cols-4'>
                            {history.sessions.slice().reverse().map((session) => (
                                <div key={`${session.session_index}-${session.started_at || ''}`} className='rounded-2xl border border-slate-200 bg-white/70 p-4 dark:border-slate-700 dark:bg-slate-950/40'>
                                    <div className='flex items-center justify-between gap-3'>
                                        <p className='text-sm font-semibold text-slate-900 dark:text-slate-100'>第 {session.session_index} 次</p>
                                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${scoreTone(Number(session.summary?.overall_score || 0))}`}>
                                            {Number(session.summary?.overall_score || 0).toFixed(1)}
                                        </span>
                                    </div>
                                    <p className='mt-3 text-sm text-slate-600 dark:text-slate-300'>
                                        {roundNameMap[session.summary?.dominant_round || ''] || session.summary?.dominant_round || '未分类'}
                                    </p>
                                </div>
                            ))}
                        </div>
                    </section>
                ) : null}

                {latest.reviews?.length ? (
                    <section className={cardClass('p-6')}>
                        <div className='mb-5 flex items-start gap-3'>
                            <div className='rounded-2xl border border-cyan-200 bg-cyan-50 p-2 text-cyan-700 dark:border-cyan-500/20 dark:bg-cyan-500/10 dark:text-cyan-200'>
                                <FileText className='h-5 w-5' />
                            </div>
                            <div>
                                <h2 className='text-xl font-bold text-slate-900 dark:text-slate-100'>最近一场单题复盘</h2>
                                <p className='mt-1 text-sm text-slate-500 dark:text-slate-400'>这里保留题目级别的反馈，便于你定位具体该练哪里。</p>
                            </div>
                        </div>
                        <div className='grid gap-4 xl:grid-cols-2'>
                            {latest.reviews.slice(0, 6).map((item, idx) => {
                                const impactedDimensions = getSpeechImpactedDimensions(item)
                                return (
                                <article key={`${item.turn_id || item.question || idx}`} className='rounded-2xl border border-slate-200 bg-white/70 p-5 dark:border-slate-700 dark:bg-slate-950/40'>
                                    <div className='flex flex-wrap items-start justify-between gap-3'>
                                        <div>
                                            <div className='flex flex-wrap gap-2'>
                                                <span className='rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'>
                                                    {roundNameMap[item.round_type || ''] || item.round_type || '未分类'}
                                                </span>
                                                {item.rubric_level ? <span className='rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400'>{item.rubric_level}</span> : null}
                                                {item.speech_used ? <span className='rounded-full bg-cyan-100 px-3 py-1 text-xs text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-200'>speech fusion</span> : null}
                                            </div>
                                            <h3 className='mt-3 text-lg font-semibold text-slate-900 dark:text-slate-100'>{item.question || '未记录题目'}</h3>
                                        </div>
                                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${scoreTone(Number(item.overall_score || latest.score))}`}>
                                            {Number(item.overall_score || latest.score).toFixed(1)}
                                        </span>
                                    </div>
                                    <p className='mt-4 line-clamp-3 text-sm leading-7 text-slate-600 dark:text-slate-300'>{item.answer || '当前未保存该题回答文本。'}</p>
                                    <div className='mt-4 grid gap-3 md:grid-cols-3'>
                                        <div className='rounded-xl border border-emerald-200 bg-emerald-50/70 p-3 dark:border-emerald-500/10 dark:bg-emerald-500/10'>
                                            <p className='text-xs uppercase tracking-[0.22em] text-emerald-700 dark:text-emerald-200/70'>亮点</p>
                                            <p className='mt-2 text-sm leading-6 text-slate-700 dark:text-emerald-50/85'>{item.summary?.strengths?.[0] || '当前未返回该题亮点总结。'}</p>
                                        </div>
                                        <div className='rounded-xl border border-amber-200 bg-amber-50/70 p-3 dark:border-amber-500/10 dark:bg-amber-500/10'>
                                            <p className='text-xs uppercase tracking-[0.22em] text-amber-700 dark:text-amber-200/70'>短板</p>
                                            <p className='mt-2 text-sm leading-6 text-slate-700 dark:text-amber-50/85'>{item.summary?.weaknesses?.[0] || '当前未返回该题短板总结。'}</p>
                                        </div>
                                        <div className='rounded-xl border border-cyan-200 bg-cyan-50/70 p-3 dark:border-cyan-500/10 dark:bg-cyan-500/10'>
                                            <p className='text-xs uppercase tracking-[0.22em] text-cyan-700 dark:text-cyan-200/70'>建议</p>
                                            <p className='mt-2 text-sm leading-6 text-slate-700 dark:text-cyan-50/85'>{item.summary?.next_actions?.[0] || '建议继续补充更细的行动建议。'}</p>
                                        </div>
                                    </div>
                                    {impactedDimensions.length > 0 ? (
                                        <div className='mt-4 rounded-2xl border border-sky-200 bg-sky-50/80 p-4 dark:border-sky-500/15 dark:bg-sky-500/10'>
                                            <div className='flex flex-wrap items-center justify-between gap-2'>
                                                <p className='text-xs uppercase tracking-[0.22em] text-sky-700 dark:text-sky-200/80'>speech impact on score</p>
                                                {item.speech_expression_score != null ? <span className='text-xs font-semibold text-sky-700 dark:text-sky-200'>expression {Number(item.speech_expression_score).toFixed(1)}</span> : null}
                                            </div>
                                            <div className='mt-3 grid gap-3 md:grid-cols-2'>
                                                {impactedDimensions.map(dim => (
                                                    <div key={`${item.turn_id || idx}-${dim.key || dim.label}`} className='rounded-xl border border-white/70 bg-white/80 p-3 dark:border-slate-700 dark:bg-slate-950/40'>
                                                        <p className='text-sm font-semibold text-slate-900 dark:text-slate-100'>{dim.label || dim.key}</p>
                                                        <div className='mt-2 flex flex-wrap gap-2 text-xs text-slate-600 dark:text-slate-300'>
                                                            <span>text {Number(dim.text_base_score || 0).toFixed(1)}</span>
                                                            <span>{Number(dim.speech_adjustment || 0) >= 0 ? '+' : ''}{Number(dim.speech_adjustment || 0).toFixed(1)}</span>
                                                            <span>final {Number(dim.final_score ?? dim.score ?? 0).toFixed(1)}</span>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ) : null}
                                </article>
                            )})}
                        </div>
                    </section>
                ) : null}
            </div>
        </main>
    )
}

'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
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
import { getBackendBaseUrl } from '@/lib/backend'

const BACKEND_API_BASE = getBackendBaseUrl()
const ROUND_COLORS = ['#111111', '#4C6A8A', '#B67A2D', '#7A8E63']
const FIT_GAUGE_COLORS = ['#111111', '#E8E2D7']

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
        { name: '内容轴', score: axisAverages.content ?? null, fill: '#111111' },
        { name: '表达轴', score: axisAverages.delivery ?? null, fill: '#4C6A8A' },
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

export default function InsightsPage() {
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [summary, setSummary] = useState<InsightsSummaryPayload | null>(null)

    useEffect(() => {
        const load = async () => {
            try {
                setLoading(true)
                setError('')
                const res = await fetch(`${BACKEND_API_BASE}/api/insights/summary`, { cache: 'no-store' })
                const data = await safeReadJson<InsightsSummaryPayload>(res)
                if (!res.ok || !data?.success) {
                    throw new Error(data?.error || '获取最近面试总览失败')
                }
                setSummary(data)
            } catch (loadError) {
                setError(loadError instanceof Error ? loadError.message : '获取最近面试总览失败')
            } finally {
                setLoading(false)
            }
        }

        void load()
    }, [])

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
            <div className="flex min-h-screen bg-[#FAF9F6]">
                <PersistentSidebar />
                <main className="flex-1 p-8">
                    <section className="rounded-2xl border border-[#E5E5E5] bg-white p-10 text-center shadow-sm">
                        <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-[#111111] border-t-transparent" />
                        <p className="text-sm text-[#666666]">正在汇总最近面试表现...</p>
                    </section>
                </main>
            </div>
        )
    }

    return (
        <div className="flex min-h-screen bg-[#FAF9F6]">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-7xl px-6 py-8">
                    <section className="rounded-3xl border border-[#E5E5E5] bg-[#FAF9F6] p-8 shadow-sm">
                        <p className="text-xs font-medium uppercase tracking-[0.18em] text-[#999999]">最近总览</p>
                        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#111111] sm:text-4xl">最近面试综合画像</h1>
                        <p className="mt-3 max-w-3xl text-sm leading-7 text-[#666666]">
                            上半部分看最近表现的变化，下半部分看跨轮次的综合能力、岗位贴合度和下一阶段最值得优先修正的问题。
                        </p>
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
                                                <CartesianGrid stroke="#ECE7DD" vertical={false} />
                                                <XAxis dataKey="label" tick={{ fill: '#8C867C', fontSize: 12 }} axisLine={false} tickLine={false} />
                                                <YAxis domain={[0, 100]} tick={{ fill: '#8C867C', fontSize: 12 }} axisLine={false} tickLine={false} width={34} />
                                                <Tooltip
                                                    contentStyle={{ borderRadius: 16, border: '1px solid #E5E5E5', backgroundColor: '#FFFFFF' }}
                                                    formatter={(value: unknown) => [`${formatNumber(Number(value))}`, '综合得分']}
                                                />
                                                <Line type="monotone" dataKey="score" stroke="#111111" strokeWidth={2.5} dot={{ r: 4, fill: '#111111' }} activeDot={{ r: 5 }} connectNulls />
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
                                                <Line type="monotone" dataKey="stability" name="稳定度" stroke="#111111" strokeWidth={2.4} dot={{ r: 4, fill: '#111111' }} connectNulls />
                                                <Line type="monotone" dataKey="risk" name="风险热度" stroke="#B67A2D" strokeWidth={2.2} dot={{ r: 4, fill: '#B67A2D' }} connectNulls />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                </ChartCard>
                            </section>

                            <section className="mt-6 grid gap-6 xl:grid-cols-[1.2fr_1fr]">
                                <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                                    <div className="flex items-center gap-2">
                                        <BarChart3 className="h-5 w-5 text-[#556987]" />
                                        <h2 className="text-xl font-semibold text-[#111111]">四轮综合能力画像</h2>
                                    </div>
                                    <p className="mt-2 text-sm leading-6 text-[#666666]">
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
                                                    : 'bg-[#F2F2F0] text-[#666666]'
                                                    }`}
                                            >
                                                {item.label} {item.count > 0 ? `${item.count} 场` : '样本不足'}
                                            </span>
                                        ))}
                                    </div>

                                    <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_0.95fr]">
                                        <div className="h-[320px] rounded-2xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <RadarChart data={radarDimensions}>
                                                    <PolarGrid stroke="#DDD7CA" />
                                                    <PolarAngleAxis dataKey="label" tick={{ fill: '#666666', fontSize: 12 }} />
                                                    <Radar name="综合能力" dataKey="score" stroke="#111111" fill="#111111" fillOpacity={0.16} strokeWidth={2} />
                                                    <Tooltip formatter={(value: unknown) => [`${formatNumber(Number(value))}`, '得分']} />
                                                </RadarChart>
                                            </ResponsiveContainer>
                                        </div>

                                        <div className="rounded-2xl border border-[#E5E5E5] bg-[#FAF9F6] p-5">
                                            <p className="text-sm font-medium text-[#111111]">综合画像结论</p>
                                            <p className="mt-3 text-sm leading-7 text-[#555555]">
                                                {summary.ai_summary.profile_summary || '近期样本还不足以形成稳定的综合画像结论。'}
                                            </p>

                                            <div className="mt-5 space-y-3">
                                                {radarDimensions.map((item) => (
                                                    <div key={item.key} className="rounded-xl border border-[#E5E5E5] bg-white p-3">
                                                        <div className="flex items-center justify-between gap-3">
                                                            <span className="text-sm text-[#111111]">{item.label}</span>
                                                            <span className="text-sm font-semibold text-[#111111]">{formatScore(item.score)}</span>
                                                        </div>
                                                        <div className="mt-2 h-2 overflow-hidden rounded-full bg-[#ECE7DD]">
                                                            <div className="h-full rounded-full bg-[#111111]" style={{ width: `${Math.max(0, Math.min(100, item.score))}%` }} />
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                </section>

                                <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                                    <div className="flex items-center gap-2">
                                        <Briefcase className="h-5 w-5 text-[#556987]" />
                                        <h2 className="text-xl font-semibold text-[#111111]">岗位匹配度</h2>
                                    </div>
                                    <p className="mt-2 text-sm leading-6 text-[#666666]">
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
                                        <p className="text-4xl font-semibold text-[#111111]">{formatScore(summary.cross_round_profile.fit_score)}</p>
                                        <p className="mt-2 text-sm text-[#666666]">{summary.cross_round_profile.target_position_label || '当前目标岗位'}</p>
                                    </div>

                                    <div className="mt-6 grid gap-3">
                                        {fitBreakdown.map((item) => (
                                            <div key={item.key} className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-3">
                                                <div className="flex items-center justify-between gap-2">
                                                    <span className="text-sm text-[#111111]">{item.label}</span>
                                                    <span className="text-sm font-semibold text-[#111111]">{formatScore(item.score)}</span>
                                                </div>
                                                <div className="mt-2 h-2 overflow-hidden rounded-full bg-[#ECE7DD]">
                                                    <div className="h-full rounded-full bg-[#111111]" style={{ width: `${Math.max(0, Math.min(100, Number(item.score || 0)))}%` }} />
                                                </div>
                                            </div>
                                        ))}
                                    </div>

                                    <div className="mt-5 rounded-2xl border border-[#E5E5E5] bg-[#FCFBF8] p-4">
                                        <p className="text-sm font-medium text-[#111111]">{fitSummary?.summary || '岗位匹配结论生成中'}</p>
                                        <p className="mt-2 text-sm leading-7 text-[#666666]">{fitSummary?.blocker || '当前尚未识别出明确的限制项。'}</p>
                                    </div>
                                </section>
                            </section>

                            <section className="mt-6 grid gap-6 xl:grid-cols-[1fr_1fr]">
                                <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                                    <div className="flex items-center gap-2">
                                        <Target className="h-5 w-5 text-[#556987]" />
                                        <h2 className="text-xl font-semibold text-[#111111]">最大短板</h2>
                                    </div>
                                    <p className="mt-2 text-sm leading-6 text-[#666666]">
                                        近期四轮样本中重复出现、并且持续拖累岗位匹配判断的主短板。
                                    </p>

                                    <div className="mt-5 rounded-2xl border border-[#E5E5E5] bg-[#FAF9F6] p-5">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className="rounded-full bg-[#FCEBE9] px-3 py-1 text-xs text-[#9D3A2E]">综合诊断</span>
                                            <h3 className="text-lg font-semibold text-[#111111]">{aiPrimaryGap?.title || '综合短板待补充'}</h3>
                                        </div>
                                        <div className="mt-4 rounded-2xl border border-[#E5E5E5] bg-white p-5">
                                            <p className="text-[15px] leading-8 text-[#555555]">
                                                {aiPrimaryGap?.description || aiPrimaryGap?.summary || aiPrimaryGap?.reason || '近期有效样本仍偏少，暂时还没有稳定重复出现的主短板结论。'}
                                            </p>
                                        </div>

                                        {(gapImpactedRounds.length > 0 || gapManifestations.length > 0 || aiPrimaryGap?.focus) ? (
                                            <div className="mt-4 grid gap-3 md:grid-cols-[1.1fr_0.9fr]">
                                                <div className="rounded-2xl border border-[#E5E5E5] bg-white p-4">
                                                    <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#999999]">主要体现</p>
                                                    {gapImpactedRounds.length > 0 ? (
                                                        <p className="mt-3 text-sm leading-7 text-[#555555]">
                                                            这个问题当前最明显地出现在
                                                            {gapImpactedRounds.map((item, index) => (
                                                                <span key={item} className="font-medium text-[#111111]">
                                                                    {`${index === 0 ? '' : '、'}${item}`}
                                                                </span>
                                                            ))}
                                                            ，说明它不是某一场的偶发现象，而是跨轮次重复出现的短板。
                                                        </p>
                                                    ) : (
                                                        <p className="mt-3 text-sm leading-7 text-[#555555]">
                                                            这个问题已经开始跨场次重复出现，建议尽早把它从“偶发问题”变成“可控问题”。
                                                        </p>
                                                    )}
                                                    {gapManifestations.length > 0 ? (
                                                        <div className="mt-4 space-y-2">
                                                            {gapManifestations.slice(0, 2).map((item, index) => (
                                                                <div key={`${item}-${index}`} className="rounded-xl border border-[#EFEAE1] bg-[#FCFBF8] px-4 py-3 text-sm leading-7 text-[#555555]">
                                                                    {item}
                                                                </div>
                                                            ))}
                                                        </div>
                                                    ) : null}
                                                </div>

                                                <div className="rounded-2xl border border-[#E5E5E5] bg-white p-4">
                                                    <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#999999]">优先改法</p>
                                                    <p className="mt-3 text-sm leading-7 text-[#555555]">
                                                        {aiPrimaryGap?.focus || '下一阶段建议先用高频轮次做专项训练，把这个问题从反复出现变成可控项。'}
                                                    </p>
                                                </div>
                                            </div>
                                        ) : null}

                                        {aiPrimaryGap?.impact ? (
                                            <div className="mt-4 rounded-2xl border border-dashed border-[#D8D4CA] bg-[#FCFBF8] p-4">
                                                <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#999999]">为什么值得优先处理</p>
                                                <p className="mt-3 text-sm leading-7 text-[#666666]">{aiPrimaryGap.impact}</p>
                                            </div>
                                        ) : null}
                                    </div>
                                </section>

                                <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                                    <div className="flex items-center gap-2">
                                        <Sparkles className="h-5 w-5 text-[#556987]" />
                                        <h2 className="text-xl font-semibold text-[#111111]">成长建议</h2>
                                    </div>
                                    <p className="mt-2 text-sm leading-6 text-[#666666]">
                                        这些建议来自近期四轮综合面试，揭示下一阶段最值得投入时间的动作。
                                    </p>

                                    <div className="mt-5 space-y-3">
                                        {growthAdvice.length > 0 ? growthAdvice.map((item, index) => (
                                            <div key={`${item.title}-${index}`} className="rounded-2xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
                                                <p className="text-sm font-medium text-[#111111]">{item.title || `建议 ${index + 1}`}</p>
                                                <p className="mt-2 text-sm leading-7 text-[#555555]">{item.advice || '暂时没有可执行建议。'}</p>
                                            </div>
                                        )) : (
                                            <div className="rounded-2xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] p-4 text-sm text-[#666666]">
                                                当前还没有足够的聚合证据来生成成长建议。
                                            </div>
                                        )}
                                    </div>
                                </section>
                            </section>

                            {recommendedReview ? (
                                <section className="mt-6 rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                                    <div className="flex flex-wrap items-center justify-between gap-4">
                                        <div className="max-w-3xl">
                                            <p className="text-sm font-medium text-[#999999]">建议优先复盘</p>
                                            <div className="mt-2 flex flex-wrap items-center gap-3">
                                                <h2 className="text-2xl font-semibold text-[#111111]">{recommendedReview.round_label}</h2>
                                                <span className="rounded-full bg-[#F3EFE4] px-3 py-1 text-xs text-[#6A5A2B]">
                                                    {formatDate(recommendedReview.created_at)}
                                                </span>
                                                <span className="rounded-full border border-[#E5E5E5] bg-white px-3 py-1 text-xs text-[#555555]">
                                                    综合得分 {formatScore(recommendedReview.score)}
                                                </span>
                                            </div>
                                            <p className="mt-3 text-sm leading-7 text-[#666666]">{recommendedReview.reason}</p>
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
        <div className="rounded-2xl border border-[#E5E5E5] bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2 text-sm text-[#666666]">
                {icon}
                <span>{title}</span>
            </div>
            <p className="mt-4 text-3xl font-semibold text-[#111111]">{value}</p>
            <p className="mt-2 text-sm leading-6 text-[#777777]">{hint}</p>
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
        <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold text-[#111111]">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-[#666666]">{description}</p>
            <div className="mt-5">{children}</div>
        </section>
    )
}

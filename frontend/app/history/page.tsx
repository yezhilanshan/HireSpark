'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, CalendarDays, FileText, Filter, Search, Timer, TrendingUp } from 'lucide-react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import PersistentSidebar from '@/components/PersistentSidebar'

const BACKEND_API_BASE = (process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000').replace(/\/$/, '')

type InterviewRecord = {
    interview_id: string
    created_at?: string
    start_time?: string
    end_time?: string
    duration?: number
    events_count?: number
    risk_level?: string
    overall_score?: number | null
    score_source?: string
    scored_turns?: number
}

type InterviewApiResult = {
    success: boolean
    interviews: InterviewRecord[]
    error?: string
}

type TrendPoint = {
    label: string
    score: number
}

function formatDate(value?: string): string {
    if (!value) return '未知时间'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return value
    return date.toLocaleString('zh-CN')
}

function formatDuration(seconds?: number): string {
    const safe = Math.max(0, Number(seconds || 0))
    if (!safe) return '未记录'
    const min = Math.floor(safe / 60)
    const sec = safe % 60
    if (min <= 0) return `${sec}秒`
    return `${min}分${sec}秒`
}

function toTime(value?: string): number {
    if (!value) return 0
    const time = new Date(value).getTime()
    return Number.isNaN(time) ? 0 : time
}

function formatTrendLabel(value?: string): string {
    if (!value) return '--'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return '--'
    return `${date.getMonth() + 1}/${date.getDate()}`
}

function deriveScore(record: InterviewRecord): number | null {
    if (record.score_source !== 'structured_evaluation') return null
    const raw = Number(record.overall_score)
    if (!Number.isFinite(raw)) return null
    return Math.max(0, Math.min(100, Number(raw.toFixed(1))))
}

function resolveRiskLabel(riskLevel?: string): string {
    const risk = (riskLevel || '').toUpperCase()
    if (risk === 'LOW') return '稳定'
    if (risk === 'MEDIUM') return '一般'
    if (risk === 'HIGH') return '波动'
    return '未标注'
}

export default function HistoryPage() {
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [keyword, setKeyword] = useState('')
    const [records, setRecords] = useState<InterviewRecord[]>([])
    const [chartReady, setChartReady] = useState(false)

    useEffect(() => {
        const load = async () => {
            try {
                const res = await fetch(`${BACKEND_API_BASE}/api/interviews?limit=80`, { cache: 'no-store' })
                const data: InterviewApiResult = await res.json()
                if (!res.ok || !data.success) {
                    throw new Error(data.error || '加载历史记录失败')
                }
                setRecords(Array.isArray(data.interviews) ? data.interviews : [])
            } catch (e) {
                setError(e instanceof Error ? e.message : '加载历史记录失败')
            } finally {
                setLoading(false)
            }
        }

        load()
    }, [])

    useEffect(() => {
        const timer = window.setTimeout(() => {
            setChartReady(true)
        }, 120)
        return () => window.clearTimeout(timer)
    }, [])

    const filtered = useMemo(() => {
        const key = keyword.trim().toLowerCase()
        if (!key) return records
        return records.filter((item) => {
            const id = (item.interview_id || '').toLowerCase()
            const risk = (item.risk_level || '').toLowerCase()
            return id.includes(key) || risk.includes(key)
        })
    }, [records, keyword])

    const trendData = useMemo<TrendPoint[]>(() => {
        if (!filtered.length) return []
        const sorted = [...filtered].sort((a, b) => {
            return toTime(a.created_at || a.start_time) - toTime(b.created_at || b.start_time)
        })

        return sorted
            .map((item) => ({
                label: formatTrendLabel(item.created_at || item.start_time),
                score: deriveScore(item),
            }))
            .filter((item): item is TrendPoint => item.score !== null)
            .slice(-6)
    }, [filtered])

    const listItems = useMemo(() => {
        return [...filtered]
            .sort((a, b) => toTime(b.created_at || b.start_time) - toTime(a.created_at || a.start_time))
            .map((item) => ({
                ...item,
                score: deriveScore(item),
            }))
    }, [filtered])

    return (
        <div className="flex min-h-screen">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-6xl px-6 py-8">
                    <section className="rounded-3xl border border-[#E5E5E5] bg-[#FAF9F6] p-8 shadow-sm">
                        <div className="flex flex-wrap items-start justify-between gap-4">
                            <div>
                                <p className="text-xs font-medium uppercase tracking-[0.18em] text-[#999999]">Interview History</p>
                                <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#111111] sm:text-4xl">历史记录</h1>
                                <p className="mt-2 text-base text-[#666666]">查看每一次面试的报告结果，并追踪整体趋势。</p>
                            </div>

                            <div className="flex w-full flex-wrap items-center gap-3 sm:w-auto">
                                <div className="relative min-w-[250px] flex-1 sm:w-[320px] sm:flex-none">
                                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#999999]" />
                                    <input
                                        aria-label="搜索会话"
                                        value={keyword}
                                        onChange={(event) => setKeyword(event.target.value)}
                                        placeholder="Search sessions or tags..."
                                        className="w-full rounded-xl border border-[#E5E5E5] bg-white py-2.5 pl-9 pr-3 text-sm text-[#111111] outline-none transition focus:border-[#111111]"
                                    />
                                </div>
                                <button className="inline-flex items-center gap-2 rounded-xl border border-[#E5E5E5] bg-white px-4 py-2.5 text-sm font-medium text-[#111111] hover:bg-[#F6F6F6]">
                                    <Filter className="h-4 w-4" />
                                    Filter
                                </button>
                            </div>
                        </div>
                    </section>

                    {loading ? (
                        <section className="mt-6 rounded-2xl border border-[#E5E5E5] bg-white p-10 text-center shadow-sm">
                            <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-[#111111] border-t-transparent" />
                            <p className="text-sm text-[#666666]">正在加载历史记录...</p>
                        </section>
                    ) : error ? (
                        <section className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-6 shadow-sm">
                            <p className="text-sm font-semibold text-red-700">{error}</p>
                        </section>
                    ) : listItems.length === 0 ? (
                        <section className="mt-6 rounded-2xl border border-[#E5E5E5] bg-white p-8 text-center shadow-sm">
                            <FileText className="mx-auto h-10 w-10 text-[#999999]" />
                            <p className="mt-3 text-sm text-[#666666]">当前没有符合筛选条件的记录。</p>
                        </section>
                    ) : (
                        <>
                            <section className={`mt-6 overflow-hidden rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm transition-all duration-700 ${chartReady ? 'translate-y-0 opacity-100' : 'translate-y-3 opacity-0'}`}>
                                <div className="mb-5 flex items-center gap-2 text-[#111111]">
                                    <TrendingUp className="h-4 w-4" />
                                    <h2 className="text-xl font-semibold">最近几次面试趋势</h2>
                                </div>

                                <div className="h-[250px] w-full">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart key={chartReady ? 'chart-ready' : 'chart-init'} data={trendData} margin={{ left: 8, right: 16, top: 10, bottom: 2 }}>
                                            <CartesianGrid stroke="#ECECEC" vertical={false} />
                                            <XAxis dataKey="label" tick={{ fill: '#9A948A', fontSize: 12 }} axisLine={false} tickLine={false} />
                                            <YAxis domain={[60, 100]} tick={{ fill: '#9A948A', fontSize: 12 }} axisLine={false} tickLine={false} width={34} />
                                            <Tooltip
                                                cursor={{ stroke: '#D9D6CE', strokeDasharray: '4 4' }}
                                                contentStyle={{ borderRadius: '12px', border: '1px solid #E5E5E5', backgroundColor: '#FFFFFF' }}
                                                formatter={(value: number) => [`${Number(value).toFixed(1)}`, 'Score']}
                                            />
                                            <Line
                                                type="monotone"
                                                dataKey="score"
                                                stroke="#111111"
                                                strokeWidth={2.5}
                                                dot={{ r: 4, fill: '#111111' }}
                                                activeDot={{ r: 5 }}
                                                isAnimationActive={chartReady}
                                                animationDuration={1200}
                                                animationEasing="ease-out"
                                            />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            </section>

                            <section className="mt-6 grid gap-5">
                                {listItems.map((item) => {
                                    const shortId = (item.interview_id || '').slice(0, 8) || 'Session'
                                    return (
                                        <article key={item.interview_id} className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm transition hover:shadow-md">
                                            <div className="flex flex-wrap items-center justify-between gap-4">
                                                <div className="min-w-0 flex-1">
                                                    <h3 className="truncate text-2xl font-semibold tracking-tight text-[#111111]">面试会话 {shortId}</h3>
                                                    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-[#666666]">
                                                        <span className="inline-flex items-center gap-2"><CalendarDays className="h-4 w-4" />{formatDate(item.created_at || item.start_time)}</span>
                                                        <span className="inline-flex items-center gap-2"><Timer className="h-4 w-4" />{formatDuration(item.duration)}</span>
                                                        <span>{resolveRiskLabel(item.risk_level)}</span>
                                                    </div>

                                                    <div className="mt-3 flex flex-wrap items-center gap-2">
                                                        <span className="rounded-full border border-[#E5E5E5] bg-[#F7F6F3] px-3 py-1 text-xs text-[#6E695F]">事件数 {Math.max(0, Number(item.events_count || 0))}</span>
                                                        <span className="rounded-full border border-[#E5E5E5] bg-[#F7F6F3] px-3 py-1 text-xs text-[#6E695F]">{item.interview_id || '-'}</span>
                                                    </div>

                                                    <div className="mt-4 flex flex-wrap gap-2">
                                                        <Link href={`/report?interviewId=${encodeURIComponent(item.interview_id || '')}`} className="inline-flex items-center gap-2 rounded-lg bg-[#111111] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#222222]">
                                                            查看报告
                                                        </Link>
                                                    </div>
                                                </div>

                                                <div className="flex items-center gap-3">
                                                    <div className="text-right">
                                                        <p className="text-4xl font-semibold text-[#111111]">{item.score === null ? '--' : item.score.toFixed(1)}</p>
                                                        <p className="text-xs uppercase tracking-[0.18em] text-[#999999]">Score</p>
                                                    </div>
                                                    <Link
                                                        href={`/report?interviewId=${encodeURIComponent(item.interview_id || '')}`}
                                                        aria-label="查看报告详情"
                                                        className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[#E5E5E5] text-[#111111] transition hover:bg-[#F5F5F5]"
                                                    >
                                                        <ArrowRight className="h-4 w-4" />
                                                    </Link>
                                                </div>
                                            </div>
                                        </article>
                                    )
                                })}
                            </section>

                            <div className="mt-6">
                                <Link href="/interview/setup" className="inline-flex items-center gap-2 rounded-lg bg-[#111111] px-5 py-2.5 text-sm font-medium text-white hover:bg-[#222222]">
                                    开始新面试
                                </Link>
                            </div>
                        </>
                    )}
                </div>
            </main>
        </div>
    )
}


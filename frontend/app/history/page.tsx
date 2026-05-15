'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, CalendarDays, FileText, Filter, Search, Tag, Timer, TrendingUp } from 'lucide-react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import PersistentSidebar from '@/components/PersistentSidebar'
import { getBackendBaseUrl } from '@/lib/backend'
import { readPageCache, writePageCache } from '@/lib/page-cache'

const BACKEND_API_BASE = getBackendBaseUrl()
const DEFAULT_HISTORY_LIMIT = 10
const HISTORY_CACHE_KEY = 'zhiyuexingchen.page.history.v1'
const HISTORY_CACHE_TTL_MS = 1000 * 60 * 20

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
    dominant_round?: string
    round_type?: string
}

type InterviewApiResult = {
    success: boolean
    interviews: InterviewRecord[]
    error?: string
}

type HistoryCacheData = {
    records: InterviewRecord[]
}

type TrendPoint = {
    label: string
    score: number
}

const BEIJING_TIME_ZONE = 'Asia/Shanghai'

const beijingDateTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
    timeZone: BEIJING_TIME_ZONE,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
})

const beijingMonthDayFormatter = new Intl.DateTimeFormat('zh-CN', {
    timeZone: BEIJING_TIME_ZONE,
    month: 'numeric',
    day: 'numeric',
})

function parseRecordDate(value?: string): Date | null {
    if (!value) return null
    const text = value.trim()
    if (!text) return null

    const hasExplicitTimeZone = /(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(text)
    if (hasExplicitTimeZone) {
        const date = new Date(text)
        return Number.isNaN(date.getTime()) ? null : date
    }

    const match = text.match(
        /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?$/
    )
    if (!match) {
        const fallback = new Date(text)
        return Number.isNaN(fallback.getTime()) ? null : fallback
    }

    const [, year, month, day, hour = '0', minute = '0', second = '0'] = match
    // SQLite CURRENT_TIMESTAMP returns local time, so we don't need to adjust for timezone
    // Just parse the date as-is and let the formatter handle timezone conversion
    const date = new Date(
        Number(year),
        Number(month) - 1,
        Number(day),
        Number(hour),
        Number(minute),
        Number(second)
    )
    return Number.isNaN(date.getTime()) ? null : date
}

function formatDate(value?: string): string {
    if (!value) return '未知时间'
    const date = parseRecordDate(value)
    if (!date) return value
    return beijingDateTimeFormatter.format(date)
}

function formatDuration(seconds?: number): string {
    const safe = Math.max(0, Math.round(Number(seconds || 0)))
    if (!safe) return '未记录'
    const min = Math.floor(safe / 60)
    const sec = safe % 60
    if (min <= 0) return `${sec}秒`
    return `${min}分${sec}秒`
}

function toTime(value?: string): number {
    const date = parseRecordDate(value)
    return date ? date.getTime() : 0
}

function formatTrendLabel(value?: string): string {
    if (!value) return '--'
    const date = parseRecordDate(value)
    if (!date) return '--'
    return beijingMonthDayFormatter.format(date)
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

function roundLabel(roundType?: string): string {
    const normalized = String(roundType || '').trim().toLowerCase()
    if (normalized === 'technical') return '基础知识面'
    if (normalized === 'project') return '项目面'
    if (normalized === 'system_design') return '系统设计面'
    if (normalized === 'hr') return 'HR 面'
    return '未标记轮次'
}

export default function HistoryPage() {
    const initialCache = typeof window === 'undefined'
        ? null
        : readPageCache<HistoryCacheData>(HISTORY_CACHE_KEY, HISTORY_CACHE_TTL_MS)
    const hasCachedRecords = Boolean(initialCache?.records?.length)

    const [loading, setLoading] = useState(!initialCache)
    const [error, setError] = useState('')
    const [keyword, setKeyword] = useState('')
    const [records, setRecords] = useState<InterviewRecord[]>(initialCache?.records || [])
    const [showAllRecords, setShowAllRecords] = useState(false)
    const [chartReady, setChartReady] = useState(false)

    useEffect(() => {
        const load = async () => {
            try {
                if (!hasCachedRecords) {
                    setLoading(true)
                }
                setError('')

                const res = await fetch(`${BACKEND_API_BASE}/api/interviews?limit=80`, { cache: 'no-store' })
                const data: InterviewApiResult = await res.json()
                if (!res.ok || !data.success) {
                    throw new Error(data.error || '加载历史记录失败')
                }
                const nextRecords = Array.isArray(data.interviews) ? data.interviews : []
                setRecords(nextRecords)
                writePageCache<HistoryCacheData>(HISTORY_CACHE_KEY, { records: nextRecords })
            } catch (e) {
                if (hasCachedRecords) {
                    setError('历史记录更新失败，已展示缓存数据。')
                } else {
                    setError(e instanceof Error ? e.message : '加载历史记录失败')
                }
            } finally {
                setLoading(false)
            }
        }

        void load()
    }, [])

    useEffect(() => {
        const timer = window.setTimeout(() => {
            setChartReady(true)
        }, 120)
        return () => window.clearTimeout(timer)
    }, [])

    useEffect(() => {
        setShowAllRecords(false)
    }, [keyword])

    const filtered = useMemo(() => {
        const key = keyword.trim().toLowerCase()
        if (!key) return records
        return records.filter((item) => {
            const id = (item.interview_id || '').toLowerCase()
            const risk = (item.risk_level || '').toLowerCase()
            const round = roundLabel(item.dominant_round || item.round_type).toLowerCase()
            return id.includes(key) || risk.includes(key) || round.includes(key)
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
                roundLabel: roundLabel(item.dominant_round || item.round_type),
            }))
            .filter((item): item is (InterviewRecord & { score: number; roundLabel: string }) => item.score !== null)
    }, [filtered])

    const visibleListItems = useMemo(() => {
        return showAllRecords ? listItems : listItems.slice(0, DEFAULT_HISTORY_LIMIT)
    }, [listItems, showAllRecords])

    const hasMoreRecords = listItems.length > DEFAULT_HISTORY_LIMIT

    return (
        <div className="flex min-h-screen">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-6xl px-6 py-8">
                    <section className="rounded-3xl border border-[var(--border)] bg-[var(--surface)] p-8 shadow-sm">
                        <div className="flex flex-wrap items-start justify-between gap-4">
                            <div>
                                <p className="text-xs font-medium uppercase tracking-[0.18em] text-[var(--ink-lighter)]">面试历史</p>
                                <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--ink)] sm:text-4xl">历史记录</h1>
                                <p className="mt-2 text-base text-[var(--ink-muted)]">查看每一次面试的报告结果，并追踪整体趋势。</p>
                            </div>

                            <div className="flex w-full flex-wrap items-center gap-3 sm:w-auto">
                                <div className="relative min-w-[250px] flex-1 sm:w-[320px] sm:flex-none">
                                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--ink-lighter)]" />
                                    <input
                                        aria-label="搜索会话"
                                        value={keyword}
                                        onChange={(event) => setKeyword(event.target.value)}
                                        placeholder="搜索会话或标签..."
                                        className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] py-2.5 pl-9 pr-3 text-sm text-[var(--ink)] outline-none transition focus:border-[var(--ink)]"
                                    />
                                </div>
                                <button className="inline-flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-2.5 text-sm font-medium text-[var(--ink)] hover:bg-[var(--accent)]">
                                    <Filter className="h-4 w-4" />
                                    Filter
                                </button>
                            </div>
                        </div>
                    </section>

                    {loading ? (
                        <section className="mt-6 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-10 text-center shadow-sm">
                            <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-[var(--ink)] border-t-transparent" />
                            <p className="text-sm text-[var(--ink-muted)]">正在加载历史记录...</p>
                        </section>
                    ) : error ? (
                        <section className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-6 shadow-sm">
                            <p className="text-sm font-semibold text-red-700">{error}</p>
                        </section>
                    ) : listItems.length === 0 ? (
                        <section className="mt-6 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-8 text-center shadow-sm">
                            <FileText className="mx-auto h-10 w-10 text-[var(--ink-lighter)]" />
                            <p className="mt-3 text-sm text-[var(--ink-muted)]">当前没有符合筛选条件的已评分记录。</p>
                        </section>
                    ) : (
                        <>
                            <section className={`mt-6 overflow-hidden rounded-3xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-sm transition-all duration-700 ${chartReady ? 'translate-y-0 opacity-100' : 'translate-y-3 opacity-0'}`}>
                                <div className="mb-5 flex items-center gap-2 text-[var(--ink)]">
                                    <TrendingUp className="h-4 w-4" />
                                    <h2 className="text-xl font-semibold">最近几次面试趋势</h2>
                                </div>

                                <div className="h-[250px] w-full">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart key={chartReady ? 'chart-ready' : 'chart-init'} data={trendData} margin={{ left: 8, right: 16, top: 10, bottom: 2 }}>
                                            <CartesianGrid stroke="var(--border)" vertical={false} />
                                            <XAxis dataKey="label" tick={{ fill: 'var(--ink-muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
                                            <YAxis domain={[60, 100]} tick={{ fill: 'var(--ink-muted)', fontSize: 12 }} axisLine={false} tickLine={false} width={34} />
                                            <Tooltip
                                                cursor={{ stroke: 'var(--ink-muted)', strokeDasharray: '4 4' }}
                                                contentStyle={{ borderRadius: '12px', border: '1px solid var(--border)', backgroundColor: 'var(--surface)' }}
                                                formatter={(value: number) => [`${Number(value).toFixed(1)}`, '得分']}
                                            />
                                            <Line
                                                type="monotone"
                                                dataKey="score"
                                                stroke="var(--ink)"
                                                strokeWidth={2.5}
                                                dot={{ r: 4, fill: 'var(--ink)' }}
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
                                {visibleListItems.map((item) => {
                                    return (
                                        <article key={item.interview_id} className="rounded-3xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-sm transition hover:shadow-md">
                                            <div className="flex flex-wrap items-center justify-between gap-4">
                                                <div className="min-w-0 flex-1 [&>h3]:hidden">
                                                    <p className="truncate text-2xl font-semibold tracking-tight text-[var(--ink)]">{item.roundLabel}</p>
                                                    <h3 className="truncate text-2xl font-semibold tracking-tight text-[var(--ink)]">面试会话</h3>
                                                    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-[var(--ink-muted)]">
                                                        <span className="inline-flex items-center gap-2"><CalendarDays className="h-4 w-4" />{formatDate(item.created_at || item.start_time)}</span>
                                                        <span className="inline-flex items-center gap-2"><Timer className="h-4 w-4" />{formatDuration(item.duration)}</span>
                                                        <span className="inline-flex items-center gap-2"><Tag className="h-4 w-4" />{item.roundLabel}</span>
                                                        <span>{resolveRiskLabel(item.risk_level)}</span>
                                                    </div>

                                                    <div className="mt-4 flex flex-wrap gap-2">
                                                        <Link href={`/report?interviewId=${encodeURIComponent(item.interview_id || '')}`} className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-[var(--ink)] hover:bg-[var(--border)]">
                                                            查看报告
                                                        </Link>
                                                    </div>
                                                </div>

                                                <div className="flex items-center gap-3">
                                                    <div className="text-right">
                                                        <p className="text-4xl font-semibold text-[var(--ink)]">{item.score.toFixed(1)}</p>
                                                        <p className="text-xs uppercase tracking-[0.18em] text-[var(--ink-lighter)]">得分</p>
                                                    </div>
                                                    <Link
                                                        href={`/report?interviewId=${encodeURIComponent(item.interview_id || '')}`}
                                                        aria-label="查看报告详情"
                                                        className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[var(--border)] text-[var(--ink)] transition hover:bg-[var(--accent)]"
                                                    >
                                                        <ArrowRight className="h-4 w-4" />
                                                    </Link>
                                                </div>
                                            </div>
                                        </article>
                                    )
                                })}

                                {hasMoreRecords ? (
                                    <div className="text-center">
                                        <button
                                            type="button"
                                            onClick={() => setShowAllRecords((prev) => !prev)}
                                            className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-sm font-medium text-[var(--ink)] transition hover:bg-[var(--accent)]"
                                        >
                                            {showAllRecords ? '收起记录' : `查看更多记录（+${listItems.length - DEFAULT_HISTORY_LIMIT}）`}
                                        </button>
                                    </div>
                                ) : null}
                            </section>

                        </>
                    )}
                </div>
            </main>
        </div>
    )
}


'use client'

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { ArrowRight, CalendarDays, Clock3, Film, Tag, Timer } from 'lucide-react'
import type { DeepAuditItem, ReplayPayload } from '@/types/replay'
import PersistentSidebar from '@/components/PersistentSidebar'
import { fetchWithTimeout, getBackendBaseUrl } from '@/lib/backend'
import { buildPageCacheKey, readPageCache, writePageCache } from '@/lib/page-cache'
import {
    safeNumber,
    clampNumber,
    formatMs,
    anchorLabel,
    isAnchorActive,
    normalizeCompareText,
    dimensionLabel,
    toTime,
    formatDate,
    formatDuration,
    roundLabel,
    isTypingTarget,
} from '@/lib/replay-utils'

const BACKEND_API_BASE = getBackendBaseUrl()
const DEFAULT_RECORD_LIMIT = 10
const REPLAY_LIST_CACHE_KEY = 'zhiyuexingchen.page.replay.list.v1'
const REPLAY_LIST_CACHE_TTL_MS = 1000 * 60 * 20
const REPLAY_DETAIL_CACHE_PREFIX = 'zhiyuexingchen.page.replay.detail.v1'
const REPLAY_DETAIL_CACHE_TTL_MS = 1000 * 60 * 20

function getAnchorStartMs(anchor: ReplayPayload['transcript_anchor_list'][number]): number {
    return safeNumber(anchor.question_start_ms ?? anchor.answer_start_ms ?? 0)
}

function matchesCurrentAnchor(
    item: { turn_id?: string; question?: string } | null | undefined,
    anchor: ReplayPayload['transcript_anchor_list'][number] | null
): boolean {
    if (!item || !anchor) return false
    const itemTurnId = String(item.turn_id || '').trim()
    const anchorTurnId = String(anchor.turn_id || '').trim()
    if (itemTurnId && anchorTurnId && itemTurnId === anchorTurnId) {
        return true
    }
    const itemQuestion = normalizeCompareText(item.question)
    const anchorQuestion = normalizeCompareText(anchor.question)
    return Boolean(itemQuestion && anchorQuestion && itemQuestion === anchorQuestion)
}

type InterviewRecord = {
    interview_id: string
    created_at?: string
    start_time?: string
    duration?: number
    dominant_round?: string
}

type InterviewApiResult = {
    success: boolean
    interviews: InterviewRecord[]
    error?: string
}

type ReplayListCacheData = {
    records: InterviewRecord[]
}

type ReplayDetailCacheData = {
    payload: ReplayPayload
}

type ReplayCacheState = 'none' | 'updating' | 'cached' | 'fresh'

function CacheStateBadge({ state }: { state: ReplayCacheState }) {
    // P1-1 优化: 缓存状态指示改进 - 增加视觉反馈
    if (state === 'updating') {
        return (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700 border border-amber-200">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
                正在更新数据...
            </span>
        )
    }
    if (state === 'cached') {
        return (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700 border border-amber-200" title="当前展示缓存数据，已请求最新数据">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500" />
                展示缓存数据
            </span>
        )
    }
    return null
}

function DiagnosisTags({
    factChecks,
    dimensionGaps,
    coverageRatio,
    latencyMs,
}: {
    factChecks: DeepAuditItem[]
    dimensionGaps: DeepAuditItem[]
    coverageRatio: number
    latencyMs: number
}) {
    // P1-1 优化: 诊断标签可视化 - 优先级排序 + 增强样式
    const tags: Array<{ tone: 'error' | 'warning' | 'info'; text: string; priority: number }> = []
    if ((factChecks || []).length > 0) tags.push({ tone: 'error', text: '事实性错误', priority: 1 })
    if ((dimensionGaps || []).length > 0) tags.push({ tone: 'warning', text: `${dimensionLabel(dimensionGaps?.[0]?.dimension)}薄弱`, priority: 2 })
    if (coverageRatio < 0.45) tags.push({ tone: 'warning', text: '关键词覆盖率低', priority: 3 })
    if (latencyMs > 2500) tags.push({ tone: 'info', text: '响应偏慢', priority: 4 })

    if (tags.length === 0) return null

    // 按优先级排序
    const sortedTags = tags.sort((a, b) => a.priority - b.priority)

    return (
        <div className="mt-4 flex flex-wrap gap-2">
            {sortedTags.map((tag) => (
                <span
                    key={tag.text}
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition ${
                        tag.tone === 'error'
                            ? 'bg-red-100 text-red-700 border border-red-200'
                            : tag.tone === 'warning'
                                ? 'bg-amber-100 text-amber-700 border border-amber-200'
                                : 'bg-blue-100 text-blue-700 border border-blue-200'
                    }`}
                    title={`优先级 ${tag.priority}`}
                >
                    {tag.tone === 'error' && <span className="inline-block h-1.5 w-1.5 rounded-full bg-current" />}
                    {tag.text}
                </span>
            ))}
        </div>
    )
}

function ReplayPageContent() {
    const searchParams = useSearchParams()
    const interviewId = (searchParams.get('interviewId') || '').trim()
    // P0-2 优化: 支持从报告页流转时自动定位题目
    const turnIdParam = (searchParams.get('turnId') || '').trim()
    const questionIdParam = (searchParams.get('questionId') || '').trim()
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [payload, setPayload] = useState<ReplayPayload | null>(null)
    const [records, setRecords] = useState<InterviewRecord[]>([])
    const [showAllRecords, setShowAllRecords] = useState(false)
    const [compareMode, setCompareMode] = useState(false)
    const [cacheState, setCacheState] = useState<ReplayCacheState>('none')
    const [videoDurationMs, setVideoDurationMs] = useState(0)
    const [videoCurrentMs, setVideoCurrentMs] = useState(0)
    const [selectedAnchorIndex, setSelectedAnchorIndex] = useState(-1)
    const [hasAutoLocated, setHasAutoLocated] = useState(false)
    const videoRef = useRef<HTMLVideoElement | null>(null)
    const anchorListRef = useRef<HTMLDivElement | null>(null)

    useEffect(() => {
        const load = async () => {
            const detailCacheKey = buildPageCacheKey(REPLAY_DETAIL_CACHE_PREFIX, interviewId)
            const cachedList = !interviewId
                ? readPageCache<ReplayListCacheData>(REPLAY_LIST_CACHE_KEY, REPLAY_LIST_CACHE_TTL_MS)
                : null
            const cachedDetail = interviewId
                ? readPageCache<ReplayDetailCacheData>(detailCacheKey, REPLAY_DETAIL_CACHE_TTL_MS)
                : null
            const hasCachedList = Boolean(cachedList?.records?.length)
            const hasCachedDetail = Boolean(cachedDetail?.payload)

            try {
                setError('')
                setShowAllRecords(false)
                setCompareMode(false)
                setVideoCurrentMs(0)
                setVideoDurationMs(0)
                setSelectedAnchorIndex(-1)
                setCacheState('none')

                if (!interviewId) {
                    setPayload(null)
                    if (hasCachedList) {
                        setRecords(cachedList?.records || [])
                        setLoading(false)
                        setCacheState('updating')
                    } else {
                        setRecords([])
                        setLoading(true)
                    }

                    const res = await fetchWithTimeout(`${BACKEND_API_BASE}/api/interviews?limit=80`, { cache: 'no-store' }, 10000)
                    const data: InterviewApiResult = await res.json()
                    if (!res.ok || !data.success) {
                        throw new Error(data.error || '加载复盘列表失败')
                    }
                    const nextRecords = Array.isArray(data.interviews) ? data.interviews : []
                    setRecords(nextRecords)
                    writePageCache<ReplayListCacheData>(REPLAY_LIST_CACHE_KEY, { records: nextRecords })
                    setCacheState('fresh')
                    return
                }

                setRecords([])
                if (hasCachedDetail) {
                    setPayload(cachedDetail?.payload || null)
                    setLoading(false)
                    setCacheState('updating')
                } else {
                    setPayload(null)
                    setLoading(true)
                }

                await fetchWithTimeout(`${BACKEND_API_BASE}/api/review/generate/${encodeURIComponent(interviewId)}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ force: false }),
                }, 5000).catch(() => null)

                const res = await fetchWithTimeout(`${BACKEND_API_BASE}/api/replay/${encodeURIComponent(interviewId)}`, { cache: 'no-store' }, 12000)
                const data: ReplayPayload = await res.json()
                if (!res.ok || !data.success) {
                    throw new Error(data.error || '加载复盘失败')
                }
                setPayload(data)
                writePageCache<ReplayDetailCacheData>(detailCacheKey, { payload: data })
                setCacheState('fresh')
            } catch (e) {
                if ((!interviewId && hasCachedList) || (interviewId && hasCachedDetail)) {
                    setError(interviewId ? '复盘更新失败，已展示缓存数据。' : '复盘列表更新失败，已展示缓存数据。')
                    setCacheState('cached')
                } else {
                    setError(e instanceof Error ? e.message : '加载复盘失败')
                    setCacheState('none')
                }
            } finally {
                setLoading(false)
            }
        }

        load()
    }, [interviewId])

    const orderedAnchors = useMemo(() => {
        return [...(payload?.transcript_anchor_list || [])].sort((a, b) => getAnchorStartMs(a) - getAnchorStartMs(b))
    }, [payload])

    const playUrl = useMemo(() => {
        const raw = String(payload?.video?.play_url || '').trim()
        if (!raw) return ''
        return raw.startsWith('http://') || raw.startsWith('https://') ? raw : `${BACKEND_API_BASE}${raw}`
    }, [payload])

    const videoSeekHint = useMemo(() => {
        const status = String(payload?.video?.status || '').trim().toLowerCase()
        const codec = String(payload?.video?.codec || '').trim().toLowerCase()
        if (!status && !codec) return ''
        if (status === 'transcoded' || codec === 'mp4') return ''

        if (status === 'uploaded_no_transcode') {
            return '当前视频为原始容器（未检测到 ffmpeg 转码），进度拖动可能不够精确。安装 ffmpeg 后新录制视频会自动优化。'
        }
        if (status === 'transcode_failed_raw') {
            return '当前视频转码失败，已回退为原始文件，进度拖动可能受限。请检查后端 ffmpeg 日志。'
        }
        return '当前视频不是优化后的 MP4 文件，进度拖动体验可能受限。'
    }, [payload])

    const timelineDurationMs = useMemo(() => {
        const fromPayload = safeNumber(payload?.video?.duration_ms)
        return Math.max(fromPayload, videoDurationMs, 1)
    }, [payload, videoDurationMs])

    const activeAnchorKey = useMemo(() => {
        const current = safeNumber(videoCurrentMs)
        return orderedAnchors.findIndex(item => {
            const start = getAnchorStartMs(item)
            const end = safeNumber(item.answer_end_ms ?? item.answer_start_ms ?? start)
            return isAnchorActive(current, start, end)
        })
    }, [orderedAnchors, videoCurrentMs])

    useEffect(() => {
        if (orderedAnchors.length === 0) {
            setSelectedAnchorIndex(-1)
            return
        }

        if (activeAnchorKey >= 0) {
            setSelectedAnchorIndex(activeAnchorKey)
            return
        }

        setSelectedAnchorIndex((prev) => {
            if (prev >= 0 && prev < orderedAnchors.length) return prev
            return 0
        })
    }, [activeAnchorKey, orderedAnchors])

    useEffect(() => {
        if (activeAnchorKey < 0 || !anchorListRef.current) return
        const activeButton = anchorListRef.current.querySelector<HTMLElement>(`[data-anchor-index="${activeAnchorKey}"]`)
        activeButton?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }, [activeAnchorKey])

    const currentAnchorIndex =
        selectedAnchorIndex >= 0 && selectedAnchorIndex < orderedAnchors.length
            ? selectedAnchorIndex
            : activeAnchorKey >= 0
                ? activeAnchorKey
                : orderedAnchors.length > 0
                    ? 0
                    : -1

    const currentAnchor = currentAnchorIndex >= 0 ? orderedAnchors[currentAnchorIndex] || null : null
    const currentFactChecks = currentAnchor
        ? (payload?.audits?.fact_checks || []).filter((item) => matchesCurrentAnchor(item, currentAnchor)).slice(0, 3)
        : []
    const currentDimensionGaps = currentAnchor
        ? (payload?.audits?.dimension_gaps || []).filter((item) => matchesCurrentAnchor(item, currentAnchor)).slice(0, 3)
        : []
    const currentShadowAnswer = currentAnchor
        ? (payload?.shadow_answers || []).find((item) => matchesCurrentAnchor(item, currentAnchor)) || null
        : null

    const currentLatencyMs = currentAnchor
        ? safeNumber(
            (payload?.visual_metrics?.latency_matrix?.items || []).find(
                (item) => String(item.turn_id || '').trim() === String(currentAnchor.turn_id || '').trim()
            )?.latency_ms ?? currentAnchor.latency_ms
        )
        : 0

    const currentCoverageRatio = currentAnchor
        ? safeNumber(
            (payload?.visual_metrics?.keyword_coverage?.items || []).find(
                (item) => String(item.turn_id || '').trim() === String(currentAnchor.turn_id || '').trim()
            )?.coverage_ratio
        )
        : 0

    const currentDiagnosisSummary = useMemo(() => {
        if (!currentAnchor) return '当前暂无题目诊断。'
        if (currentFactChecks.length > 0) {
            return currentFactChecks[0]?.finding || '当前题已识别到需要优先复盘的问题。'
        }
        if (currentDimensionGaps.length > 0) {
            const weakest = currentDimensionGaps[0]
            return `本题主要短板在${dimensionLabel(weakest.dimension)}，建议优先补充底层原理、结构化表达和边界说明。`
        }
        if (currentCoverageRatio < 0.45) {
            return '本题关键词覆盖偏低，说明回答命中题干核心点不足，建议先补主结论再展开。'
        }
        if (currentLatencyMs > 2500) {
            return '本题响应时延偏长，建议先给结论，再补充细节，减少长时间停顿。'
        }
        return '当前题没有明显风险信号，建议结合参考答案继续优化表达顺序和信息密度。'
    }, [currentAnchor, currentFactChecks, currentDimensionGaps, currentCoverageRatio, currentLatencyMs])

    const timelineWidthPercent = useMemo(
        () => Math.min(260, Math.max(100, orderedAnchors.length * 12)),
        [orderedAnchors.length]
    )

    // P2-1 优化: 时间轴标记重叠检测 - 改进算法确保最小间距
    const timelineLabelVisibleFlags = useMemo(() => {
        const MIN_LABEL_SPACING_PERCENT = 10 // 最小间距 10%
        const result: boolean[] = []

        if (orderedAnchors.length === 0) return result

        // 计算所有标记的位置
        const positions = orderedAnchors.map((item, idx) => ({
            idx,
            left: clampNumber((getAnchorStartMs(item) / timelineDurationMs) * 100, 0, 100),
        }))

        // 始终显示当前活跃的标记
        const visibleIndices = new Set<number>()
        if (activeAnchorKey >= 0) {
            visibleIndices.add(activeAnchorKey)
        }

        // 贪心算法：优先显示间距足够的标记
        for (const pos of positions) {
            if (visibleIndices.has(pos.idx)) continue

            const hasConflict = Array.from(visibleIndices).some((visibleIdx) => {
                const visiblePos = positions[visibleIdx]
                return Math.abs(pos.left - visiblePos.left) < MIN_LABEL_SPACING_PERCENT
            })

            if (!hasConflict) {
                visibleIndices.add(pos.idx)
            }
        }

        // 生成布尔数组
        return orderedAnchors.map((_, idx) => visibleIndices.has(idx))
    }, [orderedAnchors, timelineDurationMs, activeAnchorKey])

    const seekTo = useCallback((ms: number, anchorIndex?: number) => {
        const targetMs = clampNumber(safeNumber(ms), 0, timelineDurationMs)
        if (typeof anchorIndex === 'number' && anchorIndex >= 0) {
            setSelectedAnchorIndex(anchorIndex)
        }
        if (!videoRef.current) return
        videoRef.current.currentTime = targetMs / 1000
        setVideoCurrentMs(targetMs)
        videoRef.current.play().catch(() => undefined)
    }, [timelineDurationMs])

    useEffect(() => {
        if (!interviewId || !payload?.video?.available || !playUrl) return

        const handler = (event: KeyboardEvent) => {
            if (isTypingTarget(event.target)) return

            const currentMs = videoRef.current ? videoRef.current.currentTime * 1000 : 0

            if (event.key === 'ArrowLeft') {
                event.preventDefault()
                seekTo(currentMs - 5000)
                return
            }
            if (event.key === 'ArrowRight') {
                event.preventDefault()
                seekTo(currentMs + 5000)
                return
            }
            if (event.code === 'Space') {
                event.preventDefault()
                if (!videoRef.current) return
                if (videoRef.current.paused) {
                    videoRef.current.play().catch(() => undefined)
                } else {
                    videoRef.current.pause()
                }
            }
        }

        window.addEventListener('keydown', handler)
        return () => window.removeEventListener('keydown', handler)
    }, [interviewId, payload?.video?.available, playUrl, seekTo])

    // P0-2 优化: 从报告页流转时自动定位到目标题目
    useEffect(() => {
        if (hasAutoLocated || !payload || orderedAnchors.length === 0 || (!turnIdParam && !questionIdParam)) {
            return
        }

        let targetIndex = -1

        // 优先按 turnId 匹配
        if (turnIdParam) {
            targetIndex = orderedAnchors.findIndex(item =>
                String(item.turn_id || '').trim() === turnIdParam
            )
        }

        // 次选按 questionId 或题目内容匹配
        if (targetIndex < 0 && questionIdParam) {
            targetIndex = orderedAnchors.findIndex(item =>
                String(item.turn_id || '').trim() === questionIdParam ||
                normalizeCompareText(item.question) === normalizeCompareText(questionIdParam)
            )
        }

        if (targetIndex >= 0) {
            const targetAnchor = orderedAnchors[targetIndex]
            const startMs = getAnchorStartMs(targetAnchor)
            seekTo(startMs, targetIndex)
            setHasAutoLocated(true)
        }
    }, [payload, orderedAnchors, turnIdParam, questionIdParam, hasAutoLocated, seekTo])

    if (loading) {
        return (
            <div className="flex min-h-screen">
                <PersistentSidebar />
                <main className="flex-1 overflow-y-auto">
                    <div className="flex min-h-full items-center justify-center">
                        <div className="rounded-2xl border border-[#E5E5E5] bg-white px-8 py-10 text-center shadow-sm">
                            <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-[#111111] border-t-transparent" />
                            <p className="text-sm font-medium text-[#666666]">复盘加载中...</p>
                        </div>
                    </div>
                </main>
            </div>
        )
    }

    if (!interviewId) {
        const orderedRecords = [...records]
            .sort((a, b) => toTime(b.created_at || b.start_time) - toTime(a.created_at || a.start_time))
            .map((item) => ({
                ...item,
                _roundLabel: roundLabel(item.dominant_round),
            }))
            .filter((item) => Boolean(item._roundLabel))
        const visibleRecords = showAllRecords ? orderedRecords : orderedRecords.slice(0, DEFAULT_RECORD_LIMIT)
        const hasMoreRecords = orderedRecords.length > DEFAULT_RECORD_LIMIT

        return (
            <div className="flex min-h-screen">
                <PersistentSidebar />
                <main className="flex-1 overflow-y-auto">
                    <div className="mx-auto max-w-5xl px-6 py-8">
                        <section className="rounded-3xl border border-[#E5E5E5] bg-[#FAF9F6] p-8 shadow-sm">
                            <p className="text-xs uppercase tracking-[0.16em] text-[#999999]">面试回放</p>
                            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[#111111]">面试复盘</h1>
                            <div className="mt-2"><CacheStateBadge state={cacheState} /></div>
                        </section>

                        {error ? (
                            <section className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-6">
                                <p className="text-sm font-medium text-red-700">{error}</p>
                            </section>
                        ) : null}

                        {!error && orderedRecords.length === 0 ? (
                            <section className="mt-6 rounded-2xl border border-[#E5E5E5] bg-white p-8 text-center shadow-sm">
                                <p className="text-sm text-[#666666]">暂无已标注轮次的会话记录。</p>
                            </section>
                        ) : (
                            <section className="mt-6 grid gap-5">
                                {visibleRecords.map((item) => (
                                    <article key={item.interview_id} className="rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
                                        <div className="flex flex-wrap items-center justify-between gap-4">
                                            <div className="min-w-0 flex-1 [&>p:nth-of-type(2)]:hidden">
                                                <p className="text-lg font-semibold text-[#111111]">{item._roundLabel || '未标记轮次'}</p>
                                                <p className="text-lg font-semibold text-[#111111]">面试会话</p>
                                                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-[#666666]">
                                                    <span className="inline-flex items-center gap-2"><CalendarDays className="h-4 w-4" />{formatDate(item.created_at || item.start_time)}</span>
                                                    <span className="inline-flex items-center gap-2"><Timer className="h-4 w-4" />{formatDuration(item.duration)}</span>
                                                    <span className="inline-flex items-center gap-2"><Tag className="h-4 w-4" />{item._roundLabel}</span>
                                                </div>
                                            </div>
                                            <Link
                                                href={`/replay?interviewId=${encodeURIComponent(item.interview_id || '')}`}
                                                className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-[#111111] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#222222]"
                                            >
                                                进入复盘
                                                <ArrowRight className="h-4 w-4" />
                                            </Link>
                                        </div>
                                    </article>
                                ))}

                                {hasMoreRecords ? (
                                    <div className="pt-1 text-center">
                                        <button
                                            type="button"
                                            onClick={() => setShowAllRecords((prev) => !prev)}
                                            className="inline-flex items-center gap-2 rounded-lg border border-[#E5E5E5] bg-white px-4 py-2 text-sm font-medium text-[#333333] transition hover:bg-[#F7F6F3]"
                                        >
                                            {showAllRecords ? '收起记录' : `查看更多记录（+${orderedRecords.length - DEFAULT_RECORD_LIMIT}）`}
                                        </button>
                                    </div>
                                ) : null}
                            </section>
                        )}
                    </div>
                </main>
            </div>
        )
    }

    if (error || !payload) {
        return (
            <div className="flex min-h-screen">
                <PersistentSidebar />
                <main className="flex-1 overflow-y-auto">
                    <div className="mx-auto max-w-2xl px-6 py-8">
                        <section className="rounded-2xl border border-red-200 bg-red-50 p-8">
                            <p className="text-lg font-semibold text-red-700">复盘加载失败</p>
                            <p className="mt-2 text-sm text-red-700/90">{error || '未知错误'}</p>
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
                <div className="mx-auto max-w-7xl px-6 py-8">
                    <section className="rounded-3xl border border-[#E5E5E5] bg-[#FAF9F6] p-8 shadow-sm">
                        <p className="text-xs uppercase tracking-[0.16em] text-[#999999]">面试复盘</p>
                        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[#111111]">视频回放</h1>
                        <div className="mt-2"><CacheStateBadge state={cacheState} /></div>
                    </section>

                    <section className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(460px,1fr)]">
                        <article className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm sm:p-7">
                            <div className="mb-4 flex items-center gap-2 text-[#111111]">
                                <Film className="h-5 w-5" />
                                <h2 className="text-lg font-semibold">面试视频</h2>
                            </div>
                            {payload.video?.available && payload.video.play_url ? (
                                <>
                                    <div className="overflow-hidden rounded-2xl border border-[#E5E5E5] bg-black">
                                        <video
                                            ref={videoRef}
                                            controls
                                            preload="auto"
                                            className="aspect-video w-full bg-black"
                                            src={playUrl}
                                            onLoadedMetadata={(event) => {
                                                const duration = Number(event.currentTarget.duration || 0)
                                                if (duration > 0) {
                                                    setVideoDurationMs(Math.floor(duration * 1000))
                                                }
                                            }}
                                            onTimeUpdate={(event) => {
                                                setVideoCurrentMs(Math.floor(Number(event.currentTarget.currentTime || 0) * 1000))
                                            }}
                                        />
                                    </div>

                                    {videoSeekHint ? (
                                        <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                                            {videoSeekHint}
                                        </div>
                                    ) : null}

                                    <div className="mt-5 rounded-2xl border border-[#E5E5E5] bg-[#FAF9F6] p-5">
                                        <div className="flex flex-wrap items-center justify-between gap-2">
                                            <p className="text-sm font-medium text-[#111111]">题目时间轴</p>
                                            <p className="text-xs text-[#666666]">{formatMs(videoCurrentMs)} / {formatMs(timelineDurationMs)}</p>
                                        </div>
                                        <div className="mt-4 overflow-x-auto pb-1">
                                            <div className="relative h-14 min-w-[640px]" style={{ width: `${timelineWidthPercent}%` }}>
                                                <div className="absolute left-0 right-0 top-6 h-2 rounded-full bg-[#E4E0D8]" />
                                                <div
                                                    className="absolute left-0 top-6 h-2 rounded-full bg-[#111111]"
                                                    style={{ width: `${clampNumber((videoCurrentMs / timelineDurationMs) * 100, 0, 100)}%` }}
                                                />

                                                {orderedAnchors.map((item, idx) => {
                                                    const startMs = getAnchorStartMs(item)
                                                    const left = clampNumber((startMs / timelineDurationMs) * 100, 0, 100)
                                                    const active = idx === activeAnchorKey
                                                    const showLabel = timelineLabelVisibleFlags[idx]
                                                    return (
                                                        <button
                                                            key={`${item.turn_id}-${idx}`}
                                                            type="button"
                                                            onClick={() => seekTo(startMs, idx)}
                                                            className="absolute top-1 -translate-x-1/2"
                                                            style={{ left: `${left}%` }}
                                                            title={`${anchorLabel(idx)} ${formatMs(startMs)}`}
                                                        >
                                                            {showLabel ? (
                                                                <span className={`mb-1 block max-w-[88px] truncate rounded-full border px-2 py-0.5 text-[10px] ${active
                                                                    ? 'border-[#111111] bg-[#111111] text-white'
                                                                    : 'border-[#D9D4CA] bg-white text-[#555555]'
                                                                    }`}>
                                                                    {anchorLabel(idx)}
                                                                </span>
                                                            ) : (
                                                                <span className="mb-1 block h-[21px]" />
                                                            )}
                                                            <span className={`mx-auto block h-4 w-4 rounded-full border shadow-sm ${active
                                                                ? 'border-[#111111] bg-[#111111]'
                                                                : 'border-[#111111] bg-white hover:bg-[#111111]'
                                                                }`} />
                                                        </button>
                                                    )
                                                })}
                                            </div>
                                        </div>
                                    </div>
                                </>
                            ) : (
                                <div className="rounded-2xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] p-8 text-center text-sm text-[#666666]">
                                    当前会话无可回放视频，已自动降级为文本复盘。
                                </div>
                            )}

                        </article>

                        <article className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm xl:sticky xl:top-6 xl:max-h-[calc(100vh-72px)] xl:overflow-hidden">
                            <div className="mb-4 flex items-center justify-between">
                                <h2 className="text-xl font-semibold text-[#111111]">对话锚点</h2>
                                <span className="text-xs text-[#999999]">{orderedAnchors.length} 题</span>
                            </div>
                            <div ref={anchorListRef} className="space-y-3 overflow-y-auto pr-1 xl:max-h-[calc(100vh-166px)]">
                                {orderedAnchors.map((item, idx) => {
                                    const startMs = getAnchorStartMs(item)
                                    const active = idx === activeAnchorKey
                                    return (
                                        <button
                                            key={`${item.turn_id}-${idx}`}
                                            type="button"
                                            data-anchor-index={idx}
                                            onClick={() => seekTo(startMs, idx)}
                                            className={`w-full rounded-2xl border p-4 text-left transition ${active
                                                ? 'border-[#111111] bg-[#F3F1EC]'
                                                : 'border-[#E5E5E5] bg-[#FAF9F6] hover:bg-[#F1EFEA]'
                                                }`}
                                        >
                                            <div className="flex flex-wrap items-center justify-between gap-2">
                                                <p className="whitespace-pre-wrap break-words text-sm font-semibold text-[#111111]">
                                                    {item.question || '未记录题目'}
                                                </p>
                                                <span className="inline-flex items-center gap-1 text-xs text-[#666666]"><Clock3 className="h-3 w-3" />{formatMs(startMs)}</span>
                                            </div>
                                            <p className="mt-2 whitespace-pre-wrap break-words text-sm text-[#666666]">
                                                {item.answer || '未记录回答'}
                                            </p>
                                            <p className="mt-2 text-xs text-[#999999]">Latency {safeNumber(item.latency_ms).toFixed(0)} ms</p>
                                        </button>
                                    )
                                })}
                                {orderedAnchors.length === 0 ? (
                                    <div className="rounded-2xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] p-4 text-sm text-[#666666]">
                                        暂无对话锚点数据。
                                    </div>
                                ) : null}
                            </div>
                        </article>
                    </section>

                    <section className="mt-6 grid gap-6 lg:grid-cols-2">
                        <article className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                            <div className="flex flex-wrap items-start justify-between gap-3">
                                <div>
                                    <h3 className="text-lg font-semibold text-[#111111]">当前题诊断</h3>
                                    <p className="mt-1 text-sm text-[#666666]">
                                        {currentAnchor ? currentAnchor.question || '未记录题目' : '请选择一题查看本题诊断。'}
                                    </p>
                                </div>
                                {currentAnchor ? (
                                    <span className="rounded-full border border-[#E5E5E5] bg-[#FAF9F6] px-3 py-1 text-xs text-[#666666]">
                                        {anchorLabel(currentAnchorIndex)}
                                    </span>
                                ) : null}
                            </div>

                            {currentAnchor ? (
                                <>
                                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                                        <div className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-3">
                                            <p className="text-xs text-[#999999]">开始时间</p>
                                            <p className="mt-1 text-sm font-semibold text-[#111111]">{formatMs(getAnchorStartMs(currentAnchor))}</p>
                                        </div>
                                        <div className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-3">
                                            <p className="text-xs text-[#999999]">响应时延</p>
                                            <p className="mt-1 text-sm font-semibold text-[#111111]">{safeNumber(currentLatencyMs).toFixed(0)} ms</p>
                                        </div>
                                        <div className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-3">
                                            <p className="text-xs text-[#999999]">关键词覆盖率</p>
                                            <p className="mt-1 text-sm font-semibold text-[#111111]">{(currentCoverageRatio * 100).toFixed(1)}%</p>
                                        </div>
                                    </div>

                                    <DiagnosisTags
                                        factChecks={currentFactChecks}
                                        dimensionGaps={currentDimensionGaps}
                                        coverageRatio={currentCoverageRatio}
                                        latencyMs={currentLatencyMs}
                                    />

                                    <div className="mt-4 rounded-2xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
                                        <p className="text-sm font-semibold text-[#111111]">本题判断</p>
                                        <p className="mt-2 text-sm leading-6 text-[#555555]">{currentDiagnosisSummary}</p>
                                    </div>

                                    <div className="mt-4 space-y-3">
                                        {currentFactChecks.map((item, idx) => (
                                            <div key={`diagnosis-fact-${idx}`} className="rounded-xl border border-amber-200/70 bg-amber-50/70 p-3">
                                                <p className="text-xs font-medium text-amber-700">问题信号</p>
                                                <p className="mt-1 text-sm text-[#333333]">{item.finding || '当前题存在需要重点回放的问题。'}</p>
                                            </div>
                                        ))}
                                        {currentDimensionGaps.map((item, idx) => (
                                            <div key={`diagnosis-gap-${idx}`} className="rounded-xl border border-[#E5E5E5] bg-white p-3">
                                                <p className="text-xs font-medium text-[#666666]">
                                                    {dimensionLabel(item.dimension)}
                                                    {typeof item.score === 'number' ? ` · ${item.score.toFixed(1)} 分` : ''}
                                                </p>
                                                <p className="mt-1 text-sm text-[#333333]">{item.suggestion || '建议补充这一维度的关键论据与边界说明。'}</p>
                                            </div>
                                        ))}
                                        {currentFactChecks.length === 0 && currentDimensionGaps.length === 0 ? (
                                            <div className="rounded-xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] p-3 text-sm text-[#666666]">
                                                当前题没有额外审计告警，建议结合右侧参考答案优化表达顺序和信息密度。
                                            </div>
                                        ) : null}
                                    </div>
                                </>
                            ) : (
                                <div className="mt-4 rounded-xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] p-4 text-sm text-[#666666]">
                                    暂无当前题诊断数据。
                                </div>
                            )}
                        </article>

                        <article className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                            <div className="flex items-center justify-between gap-3">
                                <h3 className="text-lg font-semibold text-[#111111]">参考答案</h3>
                                <button
                                    type="button"
                                    onClick={() => setCompareMode((prev) => !prev)}
                                    disabled={!currentAnchor}
                                    className="rounded-lg border border-[#E5E5E5] bg-[#FAF9F6] px-3 py-1.5 text-xs font-medium text-[#333333] disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                    {compareMode ? '标准视图' : '对比视图'}
                                </button>
                            </div>
                            <div className="mt-3 space-y-3">
                                {compareMode && currentAnchor ? (
                                    <div className="grid gap-3 xl:grid-cols-2">
                                        <div className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
                                            <p className="text-xs font-medium text-[#666666]">我的回答</p>
                                            <p className="mt-2 text-sm leading-6 text-[#333333]">{currentAnchor.answer || '未记录回答'}</p>
                                        </div>
                                        <div className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
                                            <p className="text-xs font-medium text-[#666666]">参考答案</p>
                                            <p className="mt-2 text-sm leading-6 text-[#333333]">{currentShadowAnswer?.shadow_answer || '暂无优化回答'}</p>
                                        </div>
                                    </div>
                                ) : currentShadowAnswer ? (
                                    <div className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
                                        <p className="text-xs text-[#999999]">{currentShadowAnswer.question || currentAnchor?.question || '未记录题目'}</p>
                                        <p className="mt-2 text-sm leading-6 text-[#333333]">{currentShadowAnswer.shadow_answer || '暂无优化回答'}</p>
                                    </div>
                                ) : (
                                    <p className="text-sm text-[#666666]">当前题暂无参考答案草稿。</p>
                                )}

                                {compareMode && currentShadowAnswer?.why_better ? (
                                    <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm leading-6 text-blue-800">
                                        <p className="text-xs font-medium uppercase tracking-[0.08em]">优化思路</p>
                                        <p className="mt-1">{currentShadowAnswer.why_better}</p>
                                    </div>
                                ) : null}
                            </div>
                        </article>
                    </section>
                </div>
            </main>
        </div>
    )
}

function ReplayPageFallback() {
    return (
        <div className="flex min-h-screen">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="flex min-h-full items-center justify-center">
                    <div className="rounded-2xl border border-[#E5E5E5] bg-white px-8 py-10 text-center shadow-sm">
                        <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-[#111111] border-t-transparent" />
                        <p className="text-sm font-medium text-[#666666]">复盘加载中...</p>
                    </div>
                </div>
            </main>
        </div>
    )
}

export default function ReplayPage() {
    return (
        <Suspense fallback={<ReplayPageFallback />}>
            <ReplayPageContent />
        </Suspense>
    )
}

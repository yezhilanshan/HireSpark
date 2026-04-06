'use client'

import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { ArrowRight, CalendarDays, Clock3, Film, Tag, Timer, VolumeX } from 'lucide-react'
import type { ReplayPayload } from '@/types/replay'
import PersistentSidebar from '@/components/PersistentSidebar'
import { getBackendBaseUrl } from '@/lib/backend'

const BACKEND_API_BASE = getBackendBaseUrl()

function formatMs(ms?: number) {
    const safe = Math.max(0, Number(ms || 0))
    const totalSec = Math.floor(safe / 1000)
    const min = Math.floor(totalSec / 60)
    const sec = totalSec % 60
    return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function tagLabel(tagType: string) {
    if (tagType === 'high') return 'High Moment'
    if (tagType === 'low') return 'Low Moment'
    if (tagType === 'turning') return 'Turning Point'
    if (tagType === 'emotion') return 'Emotion'
    if (tagType === 'posture') return 'Posture'
    if (tagType === 'gaze') return 'Gaze'
    return tagType
}

function markerLabel(tagType: string) {
    if (tagType === 'high') return 'High'
    if (tagType === 'low') return 'Low'
    if (tagType === 'turning') return 'Turning'
    if (tagType === 'emotion') return 'Emotion'
    if (tagType === 'posture') return 'Posture'
    if (tagType === 'gaze') return 'Gaze'
    return tagType
}

function isAnchorActive(currentMs: number, startMs: number, endMs: number) {
    if (currentMs <= 0) return false
    return currentMs >= Math.max(0, startMs - 500) && currentMs <= endMs + 1000
}

type InterviewRecord = {
    interview_id: string
    created_at?: string
    start_time?: string
    duration?: number
}

type InterviewApiResult = {
    success: boolean
    interviews: InterviewRecord[]
    error?: string
}

function toTime(value?: string): number {
    if (!value) return 0
    const time = new Date(value).getTime()
    return Number.isNaN(time) ? 0 : time
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

function ReplayPageContent() {
    const searchParams = useSearchParams()
    const interviewId = (searchParams.get('interviewId') || '').trim()
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [payload, setPayload] = useState<ReplayPayload | null>(null)
    const [records, setRecords] = useState<InterviewRecord[]>([])
    const [videoDurationMs, setVideoDurationMs] = useState(0)
    const [videoCurrentMs, setVideoCurrentMs] = useState(0)
    const videoRef = useRef<HTMLVideoElement | null>(null)

    useEffect(() => {
        const load = async () => {
            try {
                setError('')
                setLoading(true)
                setVideoCurrentMs(0)
                setVideoDurationMs(0)
                if (!interviewId) {
                    const res = await fetch(`${BACKEND_API_BASE}/api/interviews?limit=80`, { cache: 'no-store' })
                    const data: InterviewApiResult = await res.json()
                    if (!res.ok || !data.success) {
                        throw new Error(data.error || '加载复盘列表失败')
                    }
                    setPayload(null)
                    setRecords(Array.isArray(data.interviews) ? data.interviews : [])
                    return
                }

                setRecords([])
                await fetch(`${BACKEND_API_BASE}/api/review/generate/${encodeURIComponent(interviewId)}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ force: false }),
                }).catch(() => null)

                const res = await fetch(`${BACKEND_API_BASE}/api/replay/${encodeURIComponent(interviewId)}`, { cache: 'no-store' })
                const data: ReplayPayload = await res.json()
                if (!res.ok || !data.success) {
                    throw new Error(data.error || '加载复盘失败')
                }
                setPayload(data)
            } catch (e) {
                setError(e instanceof Error ? e.message : '加载复盘失败')
            } finally {
                setLoading(false)
            }
        }

        load()
    }, [interviewId])

    const orderedAnchors = useMemo(() => {
        return [...(payload?.transcript_anchor_list || [])].sort((a, b) => Number(a.answer_start_ms || 0) - Number(b.answer_start_ms || 0))
    }, [payload])

    const orderedTags = useMemo(() => {
        return [...(payload?.tags || [])].sort((a, b) => Number(a.start_ms || 0) - Number(b.start_ms || 0))
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
        const fromPayload = Number(payload?.video?.duration_ms || 0)
        return Math.max(fromPayload, videoDurationMs, 1)
    }, [payload, videoDurationMs])

    const activeAnchorKey = useMemo(() => {
        const current = Number(videoCurrentMs || 0)
        return orderedAnchors.findIndex(item => {
            const start = Number(item.question_start_ms || item.answer_start_ms || 0)
            const end = Number(item.answer_end_ms || item.answer_start_ms || start)
            return isAnchorActive(current, start, end)
        })
    }, [orderedAnchors, videoCurrentMs])

    const seekTo = (ms: number) => {
        if (!videoRef.current) return
        const targetMs = Math.max(0, Number(ms || 0))
        videoRef.current.currentTime = targetMs / 1000
        setVideoCurrentMs(targetMs)
        videoRef.current.play().catch(() => undefined)
    }

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
        const orderedRecords = [...records].sort(
            (a, b) => toTime(b.created_at || b.start_time) - toTime(a.created_at || a.start_time)
        )

        return (
            <div className="flex min-h-screen">
                <PersistentSidebar />
                <main className="flex-1 overflow-y-auto">
                    <div className="mx-auto max-w-5xl px-6 py-8">
                        <section className="rounded-3xl border border-[#E5E5E5] bg-[#FAF9F6] p-8 shadow-sm">
                            <p className="text-xs uppercase tracking-[0.16em] text-[#999999]">Interview Replay</p>
                            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[#111111]">面试复盘</h1>
                            <p className="mt-3 text-base text-[#666666]">选择任一面试会话，进入"文本锚点 + 视频回放"查看逐段复盘。</p>
                        </section>

                        {error ? (
                            <section className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-6">
                                <p className="text-sm font-medium text-red-700">{error}</p>
                            </section>
                        ) : null}

                        {!error && orderedRecords.length === 0 ? (
                            <section className="mt-6 rounded-2xl border border-[#E5E5E5] bg-white p-8 text-center shadow-sm">
                                <p className="text-sm text-[#666666]">暂无可复盘的会话记录。</p>
                            </section>
                        ) : (
                            <section className="mt-6 grid gap-5">
                                {orderedRecords.map((item) => (
                                    <article key={item.interview_id} className="rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
                                        <div className="flex flex-wrap items-center justify-between gap-4">
                                            <div className="min-w-0 flex-1">
                                                <p className="text-lg font-semibold text-[#111111]">会话 {String(item.interview_id || '').slice(0, 8)}</p>
                                                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-[#666666]">
                                                    <span className="inline-flex items-center gap-2"><CalendarDays className="h-4 w-4" />{formatDate(item.created_at || item.start_time)}</span>
                                                    <span className="inline-flex items-center gap-2"><Timer className="h-4 w-4" />{formatDuration(item.duration)}</span>
                                                </div>
                                                <p className="mt-3 text-xs text-[#999999]">{item.interview_id}</p>
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
                        <p className="text-xs uppercase tracking-[0.16em] text-[#999999]">Interview Replay</p>
                        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[#111111]">文本锚点 + 视频回放</h1>
                        <p className="mt-3 text-base text-[#666666]">左侧放大回放视频，右侧查看完整对话锚点；关键节点标签已嵌入时间轴，可直接点击跳转。</p>
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
                                            <p className="text-sm font-medium text-[#111111]">关键节点时间轴</p>
                                            <p className="text-xs text-[#666666]">{formatMs(videoCurrentMs)} / {formatMs(timelineDurationMs)}</p>
                                        </div>
                                        <div className="relative mt-4 h-14">
                                            <div className="absolute left-0 right-0 top-6 h-2 rounded-full bg-[#E4E0D8]" />
                                            <div
                                                className="absolute left-0 top-6 h-2 rounded-full bg-[#111111]"
                                                style={{ width: `${Math.min(100, Math.max(0, (videoCurrentMs / timelineDurationMs) * 100))}%` }}
                                            />

                                            {(orderedTags || []).slice(0, 18).map((item, idx) => {
                                                const startMs = Number(item.start_ms || 0)
                                                const left = Math.min(100, Math.max(0, (startMs / timelineDurationMs) * 100))
                                                return (
                                                    <button
                                                        key={`${item.tag_type}-${item.start_ms}-${idx}`}
                                                        onClick={() => seekTo(startMs)}
                                                        className="absolute top-1 -translate-x-1/2"
                                                        style={{ left: `${left}%` }}
                                                        title={`${tagLabel(item.tag_type)} ${formatMs(startMs)}`}
                                                    >
                                                        <span className="mb-1 block max-w-[72px] truncate rounded-full border border-[#D9D4CA] bg-white px-2 py-0.5 text-[10px] text-[#555555]">
                                                            {markerLabel(item.tag_type)}
                                                        </span>
                                                        <span className="mx-auto block h-4 w-4 rounded-full border border-[#111111] bg-white shadow-sm hover:bg-[#111111]" />
                                                    </button>
                                                )
                                            })}
                                        </div>
                                        <div className="mt-2 flex flex-wrap gap-2">
                                            {(orderedTags || []).slice(0, 12).map((item, idx) => (
                                                <button
                                                    key={`chip-${item.tag_type}-${item.start_ms}-${idx}`}
                                                    onClick={() => seekTo(item.start_ms)}
                                                    className="inline-flex items-center gap-1 rounded-full border border-[#DDD8CE] bg-white px-3 py-1 text-xs text-[#444444] hover:bg-[#F3F1EC]"
                                                >
                                                    <Tag className="h-3 w-3" />
                                                    {tagLabel(item.tag_type)}
                                                    <span className="text-[#777777]">{formatMs(item.start_ms)}</span>
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </>
                            ) : (
                                <div className="rounded-2xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] p-8 text-center text-sm text-[#666666]">
                                    当前会话无可回放视频，已自动降级为文本复盘。
                                </div>
                            )}

                            <div className="mt-5 rounded-2xl border border-[#E5E5E5] bg-[#FAF9F6] p-5 text-sm text-[#555555]">
                                <p>平均响应时延：{Number(payload.visual_metrics?.latency_matrix?.avg_latency_ms || 0).toFixed(0)} ms</p>
                                <p className="mt-1">关键词覆盖率：{(Number(payload.visual_metrics?.keyword_coverage?.avg_coverage_ratio || 0) * 100).toFixed(1)}%</p>
                                <p className="mt-2 inline-flex items-center gap-1 rounded-full border border-[#E1DBD1] bg-white px-2.5 py-1 text-xs text-[#6A655B]">
                                    <VolumeX className="h-3.5 w-3.5" />
                                    当前部分历史视频可能无音频轨道；后续录制将统一写入麦克风声音。
                                </p>
                            </div>
                        </article>

                        <article className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm xl:sticky xl:top-6 xl:max-h-[calc(100vh-72px)] xl:overflow-hidden">
                            <div className="mb-4 flex items-center justify-between">
                                <h2 className="text-xl font-semibold text-[#111111]">对话锚点</h2>
                                <span className="text-xs text-[#999999]">{orderedAnchors.length} 题</span>
                            </div>
                            <div className="space-y-3 overflow-y-auto pr-1 xl:max-h-[calc(100vh-166px)]">
                                {orderedAnchors.map((item, idx) => {
                                    const startMs = Number(item.answer_start_ms || item.question_start_ms || 0)
                                    const active = idx === activeAnchorKey
                                    return (
                                    <button
                                        key={`${item.turn_id}-${idx}`}
                                        onClick={() => seekTo(startMs)}
                                        className={`w-full rounded-2xl border p-4 text-left transition ${
                                            active
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
                                        <p className="mt-2 text-xs text-[#999999]">Latency {Number(item.latency_ms || 0).toFixed(0)} ms</p>
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
                            <h3 className="text-lg font-semibold text-[#111111]">Deep Tech Audit</h3>
                            <div className="mt-3 space-y-2 text-sm text-[#555555]">
                                {(payload.audits?.fact_checks || []).slice(0, 6).map((item, idx) => (
                                    <p key={`fc-${idx}`}>- {item.finding}</p>
                                ))}
                                {(payload.audits?.fact_checks || []).length === 0 ? <p>暂无诊断结果。</p> : null}
                            </div>
                        </article>

                        <article className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                            <h3 className="text-lg font-semibold text-[#111111]">Shadow Answers</h3>
                            <div className="mt-3 space-y-3">
                                {(payload.shadow_answers || []).slice(0, 3).map((item, idx) => (
                                    <div key={`shadow-${idx}`} className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-3">
                                        <p className="text-xs text-[#999999]">{item.question || '未记录题目'}</p>
                                        <p className="mt-1 text-sm text-[#333333]">{item.shadow_answer || '暂无优化回答'}</p>
                                    </div>
                                ))}
                                {(payload.shadow_answers || []).length === 0 ? <p className="text-sm text-[#666666]">暂无影子回答。</p> : null}
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

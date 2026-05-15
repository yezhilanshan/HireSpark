'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import SocketClient from '@/lib/socket'
import { useFacePhysRppg } from '@/lib/facephys/useFacePhysRppg'
import { useFaceBehaviorMetrics } from '@/lib/facephys/useFaceBehaviorMetrics'
import { getBackendBaseUrl } from '@/lib/backend'
import { Mic, Loader2, ArrowRight, User, X, CheckCircle2, MessageSquare, Activity, Eye, HeartPulse, Gauge } from 'lucide-react'

const parseBooleanEnv = (value: string | undefined, fallback: boolean) => {
    if (value == null) return fallback
    const normalized = value.trim().toLowerCase()
    if (['1', 'true', 'yes', 'on'].includes(normalized)) return true
    if (['0', 'false', 'no', 'off'].includes(normalized)) return false
    return fallback
}

const parseNumberEnv = (value: string | undefined, fallback: number) => {
    if (value == null) return fallback
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : fallback
}

const BACKEND_API_BASE = getBackendBaseUrl()
const SERVER_ASR_ACTIVE_COOLDOWN_MS = parseNumberEnv(process.env.NEXT_PUBLIC_SERVER_ASR_ACTIVE_COOLDOWN_MS, 350)
const SERVER_ASR_FALLBACK_DELAY_MS = 3200
const SERVER_ASR_STALL_WINDOW_MS = 3200
const SERVER_ASR_RECHECK_DELAY_MS = 1100
const ENABLE_BROWSER_ASR_STALL_FALLBACK = false
const ASR_DEBUG_PANEL_ENABLED = false
const ASR_DEBUG_MAX_ITEMS = 120
const KNOWLEDGE_GRAPH_REFRESH_KEY = 'zhiyuexingchen:knowledge-graph:refresh'
const BASE_SILENCE_MS = 1650
const BROWSER_SILENCE_BONUS_MS = 220
const NOISY_ENV_SILENCE_BONUS_MS = 320
const MIN_ADAPTIVE_SILENCE_MS = 1650
const MAX_ADAPTIVE_SILENCE_MS = 2600
const ASR_NOISE_FLOOR_MIN = parseNumberEnv(process.env.NEXT_PUBLIC_ASR_NOISE_FLOOR_MIN, 0.001)
const ASR_NOISE_FLOOR_MAX = parseNumberEnv(process.env.NEXT_PUBLIC_ASR_NOISE_FLOOR_MAX, 0.03)
const ASR_ACTIVATION_MULTIPLIER = parseNumberEnv(process.env.NEXT_PUBLIC_ASR_ACTIVATION_MULTIPLIER, 2.35)
const ASR_ACTIVATION_MIN = parseNumberEnv(process.env.NEXT_PUBLIC_ASR_ACTIVATION_MIN, 0.008)
const ASR_ACTIVATION_MAX = parseNumberEnv(process.env.NEXT_PUBLIC_ASR_ACTIVATION_MAX, 0.04)
const ASR_FAST_START_WINDOW_MS = parseNumberEnv(process.env.NEXT_PUBLIC_ASR_FAST_START_WINDOW_MS, 2000)
const ASR_FAST_START_ACTIVATION_MULTIPLIER = parseNumberEnv(process.env.NEXT_PUBLIC_ASR_FAST_START_ACTIVATION_MULTIPLIER, 1.55)
const ASR_FAST_START_ACTIVATION_MIN = parseNumberEnv(process.env.NEXT_PUBLIC_ASR_FAST_START_ACTIVATION_MIN, 0.0045)
const ASR_FAST_START_STRONG_MULTIPLIER = parseNumberEnv(process.env.NEXT_PUBLIC_ASR_FAST_START_STRONG_MULTIPLIER, 1.08)
const ASR_HOLD_MULTIPLIER = parseNumberEnv(process.env.NEXT_PUBLIC_ASR_HOLD_MULTIPLIER, 1.65)
const ASR_HOLD_MIN = parseNumberEnv(process.env.NEXT_PUBLIC_ASR_HOLD_MIN, 0.005)
const ASR_HOLD_MAX = parseNumberEnv(process.env.NEXT_PUBLIC_ASR_HOLD_MAX, 0.028)
const ASR_STRONG_SPEECH_MULTIPLIER = parseNumberEnv(process.env.NEXT_PUBLIC_ASR_STRONG_SPEECH_MULTIPLIER, 1.22)
const ASR_AUDIO_CHUNK_MS = 100
const ASR_PREBUFFER_TARGET_MS = parseNumberEnv(process.env.NEXT_PUBLIC_ASR_PREBUFFER_TARGET_MS, 2200)
const ASR_PREBUFFER_MAX_CHUNKS = Math.max(
    8,
    Math.round(ASR_PREBUFFER_TARGET_MS / ASR_AUDIO_CHUNK_MS)
)
const ASR_CAPTURE_CONSTRAINTS: MediaTrackConstraints = {
    sampleRate: 16000,
    channelCount: 1,
    echoCancellation: parseBooleanEnv(process.env.NEXT_PUBLIC_ASR_ECHO_CANCELLATION, true),
    noiseSuppression: parseBooleanEnv(process.env.NEXT_PUBLIC_ASR_NOISE_SUPPRESSION, true),
    autoGainControl: parseBooleanEnv(process.env.NEXT_PUBLIC_ASR_AUTO_GAIN_CONTROL, true),
}

interface ChatMessage {
    role: 'interviewer' | 'candidate'
    content: string
    timestamp: string
}

interface ForcedQuestionConfig {
    id?: string
    question?: string
    category?: string
    round_type?: string
    position?: string
    difficulty?: string
}

interface InterviewConfigState {
    round: string
    roundName: string
    position: string
    difficulty: string
    selectedQuestion: ForcedQuestionConfig | null
    trainingTaskId?: string
    trainingMode?: string
    auto_end_min_questions?: number
    auto_end_max_questions?: number
}

interface AsrDebugEvent {
    event: string
    level: string
    timestamp: number
    session_id?: string
    turn_id?: string
    source?: string
    reason?: string
    reason_detail?: string
    asr_generation?: number | string
    speech_epoch?: number | string
    details?: string
    partial_preview?: string
    final_preview?: string
    segment_preview?: string
    answer_preview?: string
    text_snapshot?: string
}

interface SpeechRecognitionAlternativeLike {
    transcript: string
}

interface SpeechRecognitionResultLike {
    isFinal: boolean
    length: number
    [index: number]: SpeechRecognitionAlternativeLike
}

interface SpeechRecognitionResultListLike {
    length: number
    [index: number]: SpeechRecognitionResultLike
}

interface SpeechRecognitionEventLike extends Event {
    resultIndex: number
    results: SpeechRecognitionResultListLike
}

interface SpeechRecognitionErrorEventLike extends Event {
    error: string
    message?: string
}

interface SpeechRecognitionLike extends EventTarget {
    continuous: boolean
    interimResults: boolean
    lang: string
    onstart: ((event: Event) => void) | null
    onend: ((event: Event) => void) | null
    onresult: ((event: SpeechRecognitionEventLike) => void) | null
    onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null
    start(): void
    stop(): void
    abort(): void
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike

const getSpeechRecognitionCtor = (): SpeechRecognitionCtor | null => {
    if (typeof window === 'undefined') {
        return null
    }

    const speechWindow = window as Window & {
        SpeechRecognition?: SpeechRecognitionCtor
        webkitSpeechRecognition?: SpeechRecognitionCtor
    }

    return speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition || null
}

export default function InterviewPage() {
    const router = useRouter()
    const videoRef = useRef<HTMLVideoElement>(null)
    const cameraStreamRef = useRef<MediaStream | null>(null)
    const microphoneStreamRef = useRef<MediaStream | null>(null)
    const replayCaptureStreamRef = useRef<MediaStream | null>(null)
    const [socket, setSocket] = useState<SocketClient | null>(null)

    const [cameraReady, setCameraReady] = useState(false)
    const [interviewStarted, setInterviewStarted] = useState(false)

    // 面试配置
    const [interviewConfig, setInterviewConfig] = useState<InterviewConfigState>({
        round: 'technical',
        roundName: '技术基础面',
        position: 'java_backend',
        difficulty: 'medium',
        selectedQuestion: null,
        trainingTaskId: '',
        trainingMode: '',
        auto_end_min_questions: undefined,
        auto_end_max_questions: undefined,
    })

    // 聊天相关
    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
    const [currentQuestion, setCurrentQuestion] = useState('')
    const [userAnswer, setUserAnswer] = useState('')
    const [answerSessionStatus, setAnswerSessionStatus] = useState('idle')
    const [speechRealtimeMetrics, setSpeechRealtimeMetrics] = useState({
        is_speaking: false,
        rough_wpm: 0,
        silence_ms: 0,
        segment_index: 0,
    })
    const [finalMetricsReady, setFinalMetricsReady] = useState(false)
    const [asrDebugEvents, setAsrDebugEvents] = useState<AsrDebugEvent[]>([])
    const [showAsrDebugPanel, setShowAsrDebugPanel] = useState(true)
    const [isProcessing, setIsProcessing] = useState(false)
    const [isVoiceSupported, setIsVoiceSupported] = useState(true)
    const [isBrowserAsrSupported, setIsBrowserAsrSupported] = useState(false)
    const [isServerAsrAvailable, setIsServerAsrAvailable] = useState(true)
    const [asrStatusMessage, setAsrStatusMessage] = useState('')
    const [isListening, setIsListening] = useState(false)
    const [isAiSpeaking, setIsAiSpeaking] = useState(false)
    const [isRecording, setIsRecording] = useState(false)
    const [sessionElapsed, setSessionElapsed] = useState(0)
    const [showCompletionModal, setShowCompletionModal] = useState(false)
    const [isEndingInterview, setIsEndingInterview] = useState(false)
    const [completedInterviewId, setCompletedInterviewId] = useState('')

    // 检测数据
    const interviewStartedRef = useRef(false)
    const isAiSpeakingRef = useRef(false)
    const isRecordingRef = useRef(false)
    const isBrowserAsrSupportedRef = useRef(false)
    const isServerAsrAvailableRef = useRef(true)
    const sessionIdRef = useRef('')
    const currentTurnIdRef = useRef('')
    const interruptEpochRef = useRef(0)
    const activeTtsJobIdRef = useRef('')
    const autoEndingRef = useRef(false)
    const autoStartTriggeredRef = useRef(false)
    const pendingTtsTextRef = useRef('')
    const answerSessionIdRef = useRef('')
    const committedAnswerSessionIdsRef = useRef<Set<string>>(new Set())
    const userAnswerRef = useRef('')
    const speechActiveRef = useRef(false)
    const consecutiveSpeechFramesRef = useRef(0)
    const lastSpeechAtRef = useRef(0)
    const fastStartUntilRef = useRef(0)
    const clientSpeechEpochRef = useRef(0)
    const activeSpeechEpochRef = useRef(0)
    const speechPrebufferRef = useRef<ArrayBuffer[]>([])
    const noFaceSinceRef = useRef<number | null>(null)
    const llmTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const pendingCommitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const audioContextRef = useRef<AudioContext | null>(null)
    const audioWorkletNodeRef = useRef<AudioWorkletNode | null>(null)
    const videoRecorderRef = useRef<MediaRecorder | null>(null)
    const videoUploadIdRef = useRef('')
    const videoPartNoRef = useRef(0)
    const videoMimeTypeRef = useRef('video/webm')
    const videoFinalizeInFlightRef = useRef(false)
    const browserAsrRecognitionRef = useRef<SpeechRecognitionLike | null>(null)
    const browserAsrFallbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const browserAsrActiveRef = useRef(false)
    const browserAsrStopRequestedRef = useRef(false)
    const browserAsrFinalTextRef = useRef('')
    const browserAsrInterimTextRef = useRef('')
    const lastServerTranscriptAtRef = useRef(0)
    const serverAsrMuteUntilRef = useRef(0)
    const asrChannelRef = useRef<'none' | 'server' | 'browser'>('none')
    const noiseFloorRef = useRef(0.004)
    const answerSessionStatusRef = useRef('idle')
    const asrLockedRef = useRef(false)
    const socketRef = useRef<SocketClient | null>(null)
    const chatScrollContainerRef = useRef<HTMLDivElement | null>(null)
    const asrDebugScrollContainerRef = useRef<HTMLDivElement | null>(null)
    // TTS 音频播放
    const currentTtsAudioRef = useRef<HTMLAudioElement | null>(null)
    const currentTtsUrlRef = useRef<string | null>(null)
    const browserTtsUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null)
    const browserTtsActiveRef = useRef(false)
    const ttsAudioQueueRef = useRef<Array<{ audio: string; jobId: string; turnId: string; mimeType: string; provider?: string }>>([])
    const ttsDoneSignaledRef = useRef(false)
    const isTTSSpeakingRef = useRef(false)
    const receivedServerChunkForCurrentSpeakRef = useRef(false)
    const rppgMetrics = useFacePhysRppg(videoRef, cameraReady && interviewStarted)
    const faceBehaviorMetrics = useFaceBehaviorMetrics(videoRef, cameraReady && interviewStarted)
    const rppgMetricsRef = useRef(rppgMetrics)
    const faceBehaviorMetricsRef = useRef(faceBehaviorMetrics)

    useEffect(() => {
        rppgMetricsRef.current = rppgMetrics
    }, [rppgMetrics])

    useEffect(() => {
        faceBehaviorMetricsRef.current = faceBehaviorMetrics
    }, [faceBehaviorMetrics])

    const clearLlmTimeout = () => {
        if (llmTimeoutRef.current) {
            clearTimeout(llmTimeoutRef.current)
            llmTimeoutRef.current = null
        }
    }

    const clearPendingCommit = () => {
        if (pendingCommitTimerRef.current) {
            clearTimeout(pendingCommitTimerRef.current)
            pendingCommitTimerRef.current = null
        }
    }

    const clearBrowserAsrFallbackTimer = () => {
        if (browserAsrFallbackTimerRef.current) {
            clearTimeout(browserAsrFallbackTimerRef.current)
            browserAsrFallbackTimerRef.current = null
        }
    }

    const clearSpeechPrebuffer = () => {
        speechPrebufferRef.current = []
    }

    const pushLocalAsrDebugEvent = (event: string, fields: Partial<AsrDebugEvent> = {}) => {
        if (!ASR_DEBUG_PANEL_ENABLED) {
            return
        }
        const fallbackSpeechEpoch = activeSpeechEpochRef.current || clientSpeechEpochRef.current || ''
        const item: AsrDebugEvent = {
            event,
            level: String(fields.level || 'debug'),
            timestamp: Date.now() / 1000,
            session_id: sessionIdRef.current,
            turn_id: currentTurnIdRef.current,
            source: 'client',
            reason: fields.reason || '',
            reason_detail: fields.reason_detail || '',
            asr_generation: fields.asr_generation ?? '',
            speech_epoch: fields.speech_epoch ?? fallbackSpeechEpoch,
            details: fields.details || '',
            partial_preview: fields.partial_preview || '',
            final_preview: fields.final_preview || '',
            segment_preview: fields.segment_preview || '',
            answer_preview: fields.answer_preview || '',
            text_snapshot: fields.text_snapshot || '',
        }

        setAsrDebugEvents((prev) => {
            const next = [...prev, item]
            return next.slice(-ASR_DEBUG_MAX_ITEMS)
        })
    }

    const clamp = (value: number, min: number, max: number) => {
        return Math.min(max, Math.max(min, value))
    }

    const toFiniteNumber = (value: unknown, fallback = 0) => {
        const parsed = Number(value)
        return Number.isFinite(parsed) ? parsed : fallback
    }

    const roundMetric = (value: unknown, digits = 4, fallback: number | null = null): number | null => {
        const parsed = Number(value)
        if (!Number.isFinite(parsed)) return fallback
        const factor = 10 ** digits
        return Math.round(parsed * factor) / factor
    }

    const formatDetectionMetric = (value: unknown, digits = 1, suffix = '', fallback = '--') => {
        const parsed = Number(value)
        if (!Number.isFinite(parsed)) return fallback
        return `${parsed.toFixed(digits)}${suffix}`
    }

    const formatDetectionStatus = (status?: string) => {
        const normalized = String(status || '').trim()
        if (normalized === 'tracking') return '检测中'
        if (normalized === 'loading') return '加载中'
        if (normalized === 'unstable') return '信号弱'
        if (normalized === 'no_face') return '未检测到人脸'
        if (normalized === 'error') return '异常'
        return '待启动'
    }

    const buildInterviewId = (sessionId: string) => {
        const normalized = String(sessionId || '').trim()
        if (!normalized) return ''
        return `interview_${normalized}`
    }

    const initVideoUploadSession = async (sessionId: string, mimeType: string) => {
        const interviewId = buildInterviewId(sessionId)
        const res = await fetch(`${BACKEND_API_BASE}/api/interview/video/init`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                interview_id: interviewId,
                mime_type: mimeType,
            }),
        })
        const data = await res.json()
        if (!res.ok || !data?.success || !data?.upload_id) {
            throw new Error(data?.error || 'video upload init failed')
        }
        videoUploadIdRef.current = String(data.upload_id)
        videoPartNoRef.current = 0
    }

    const uploadVideoChunk = async (chunkBlob: Blob) => {
        const uploadId = videoUploadIdRef.current
        if (!uploadId || !chunkBlob || chunkBlob.size <= 0) {
            return
        }
        videoPartNoRef.current += 1
        const form = new FormData()
        form.append('upload_id', uploadId)
        form.append('part_no', String(videoPartNoRef.current))
        form.append('chunk', chunkBlob, `part_${videoPartNoRef.current}.bin`)

        const res = await fetch(`${BACKEND_API_BASE}/api/interview/video/chunk`, {
            method: 'POST',
            body: form,
        })
        if (!res.ok) {
            const data = await res.json().catch(() => ({}))
            throw new Error(data?.error || 'video chunk upload failed')
        }
    }

    const finalizeVideoUpload = async (sessionId: string) => {
        if (videoFinalizeInFlightRef.current) return
        const uploadId = videoUploadIdRef.current
        if (!uploadId) return
        videoFinalizeInFlightRef.current = true
        try {
            const interviewId = buildInterviewId(sessionId)
            await fetch(`${BACKEND_API_BASE}/api/interview/video/finalize`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    upload_id: uploadId,
                    interview_id: interviewId,
                }),
            })
        } catch (error) {
            console.warn('[Replay] finalize video upload failed:', error)
        } finally {
            videoUploadIdRef.current = ''
            videoPartNoRef.current = 0
            videoFinalizeInFlightRef.current = false
        }
    }

    const startVideoRecording = async (sessionId: string) => {
        if (typeof window === 'undefined' || !cameraStreamRef.current || !(window as any).MediaRecorder) {
            return
        }
        if (videoRecorderRef.current) {
            return
        }

        const cameraTrack = cameraStreamRef.current.getVideoTracks()[0]
        if (!cameraTrack) {
            console.warn('[Replay] missing camera track, skip recording')
            return
        }
        const captureTracks: MediaStreamTrack[] = [cameraTrack.clone()]
        const micTrack = microphoneStreamRef.current?.getAudioTracks?.()[0]
        if (micTrack && micTrack.readyState === 'live') {
            captureTracks.push(micTrack.clone())
        }
        const captureStream = new MediaStream(captureTracks)
        replayCaptureStreamRef.current = captureStream

        const preferredTypes = [
            'video/webm;codecs=vp9,opus',
            'video/webm;codecs=vp8,opus',
            'video/webm',
        ]
        let mimeType = 'video/webm'
        for (const candidate of preferredTypes) {
            if ((window as any).MediaRecorder.isTypeSupported?.(candidate)) {
                mimeType = candidate
                break
            }
        }
        videoMimeTypeRef.current = mimeType

        try {
            await initVideoUploadSession(sessionId, mimeType)
        } catch (error) {
            console.warn('[Replay] init video upload failed:', error)
            captureStream.getTracks().forEach(track => track.stop())
            replayCaptureStreamRef.current = null
            return
        }

        try {
            const recorder = new MediaRecorder(captureStream, { mimeType })
            videoRecorderRef.current = recorder
            recorder.ondataavailable = (event: BlobEvent) => {
                if (!event.data || event.data.size <= 0) return
                uploadVideoChunk(event.data).catch((error) => {
                    console.warn('[Replay] upload video chunk failed:', error)
                })
            }
            recorder.onerror = (event) => {
                console.warn('[Replay] media recorder error:', event)
            }
            recorder.start(4000)
            console.log('[Replay] video recording started')
        } catch (error) {
            console.warn('[Replay] start video recording failed:', error)
            captureStream.getTracks().forEach(track => track.stop())
            replayCaptureStreamRef.current = null
            videoRecorderRef.current = null
            videoUploadIdRef.current = ''
            videoPartNoRef.current = 0
        }
    }

    const stopVideoRecording = async (sessionId: string, finalize = true) => {
        const recorder = videoRecorderRef.current
        videoRecorderRef.current = null

        if (recorder && recorder.state !== 'inactive') {
            await new Promise<void>((resolve) => {
                const done = () => resolve()
                recorder.onstop = done
                try {
                    recorder.stop()
                } catch (_error) {
                    resolve()
                }
            })
        }
        if (replayCaptureStreamRef.current) {
            replayCaptureStreamRef.current.getTracks().forEach(track => track.stop())
            replayCaptureStreamRef.current = null
        }

        if (finalize && sessionId) {
            await finalizeVideoUpload(sessionId)
        } else if (!finalize) {
            videoUploadIdRef.current = ''
            videoPartNoRef.current = 0
        }
    }

    const normalizeTranscript = (value: string) => {
        return value.replace(/\s+/g, ' ').trim()
    }

    const squashStutterText = (value: string) => {
        return normalizeTranscript(value)
    }

    const mergeTranscriptWithDedup = (existingText: string, incomingText: string) => {
        const existing = squashStutterText(existingText)
        const incoming = squashStutterText(incomingText)

        if (!incoming) {
            return existing
        }
        if (!existing) {
            return incoming
        }
        if (existing.endsWith(incoming)) {
            return existing
        }
        if (incoming.startsWith(existing)) {
            return incoming
        }
        if (incoming.length >= 4 && existing.includes(incoming)) {
            return existing
        }

        const maxOverlap = Math.min(32, existing.length, incoming.length)
        for (let overlap = maxOverlap; overlap >= 3; overlap--) {
            if (existing.slice(-overlap) === incoming.slice(0, overlap)) {
                return `${existing}${incoming.slice(overlap)}`.trim()
            }
        }

        const needsSpace = /[A-Za-z0-9]$/.test(existing) && /^[A-Za-z0-9]/.test(incoming)
        return `${existing}${needsSpace ? ' ' : ''}${incoming}`.trim()
    }

    const markServerTranscriptActive = (cooldownMs = SERVER_ASR_ACTIVE_COOLDOWN_MS) => {
        const now = Date.now()
        lastServerTranscriptAtRef.current = now
        serverAsrMuteUntilRef.current = now + cooldownMs
        asrChannelRef.current = 'server'
    }

    const enqueueSpeechPrebuffer = (buffer: ArrayBuffer, maxChunks = ASR_PREBUFFER_MAX_CHUNKS) => {
        speechPrebufferRef.current.push(buffer)
        if (speechPrebufferRef.current.length > maxChunks) {
            speechPrebufferRef.current.splice(0, speechPrebufferRef.current.length - maxChunks)
        }
    }

    const setServerAsrAvailability = (available: boolean, message = '') => {
        isServerAsrAvailableRef.current = available
        setIsServerAsrAvailable(available)
        setAsrStatusMessage(message)
        if (!available) {
            serverAsrMuteUntilRef.current = 0
            if (asrChannelRef.current === 'server') {
                asrChannelRef.current = 'none'
            }
        }
    }

    const setBrowserAsrAvailability = (available: boolean, message = '') => {
        isBrowserAsrSupportedRef.current = available
        setIsBrowserAsrSupported(available)
        if (!available && message && !isServerAsrAvailableRef.current) {
            setAsrStatusMessage(message)
        }
    }

    const isAnswerAsrLocked = () => {
        return asrLockedRef.current || ['finalizing', 'finalized'].includes(answerSessionStatusRef.current)
    }

    const appendCandidateMessage = (content: string) => {
        const normalized = content.trim()
        if (!normalized) {
            return
        }

        setChatMessages(prev => {
            const lastMessage = prev[prev.length - 1]
            if (lastMessage?.role === 'candidate' && lastMessage.content.trim() === normalized) {
                return prev
            }

            return [...prev, {
                role: 'candidate',
                content: normalized,
                timestamp: new Date().toLocaleTimeString()
            }]
        })
    }

    const resetAnswerSessionUi = () => {
        answerSessionIdRef.current = ''
        committedAnswerSessionIdsRef.current.clear()
        asrLockedRef.current = false
        asrChannelRef.current = 'none'
        serverAsrMuteUntilRef.current = 0
        browserAsrFinalTextRef.current = ''
        browserAsrInterimTextRef.current = ''
        setAnswerSessionStatus('idle')
        setFinalMetricsReady(false)
        setSpeechRealtimeMetrics({
            is_speaking: false,
            rough_wpm: 0,
            silence_ms: 0,
            segment_index: 0,
        })
    }

    const finalizeCurrentTtsPlayback = () => {
        pendingTtsTextRef.current = ''
        receivedServerChunkForCurrentSpeakRef.current = false
        ttsDoneSignaledRef.current = false
        isTTSSpeakingRef.current = false
        isAiSpeakingRef.current = false
        setIsAiSpeaking(false)
        resumeAudioRecordingAfterTts()
    }

    const stopCurrentTts = () => {
        ttsAudioQueueRef.current = []
        pendingTtsTextRef.current = ''
        receivedServerChunkForCurrentSpeakRef.current = false
        ttsDoneSignaledRef.current = false
        isTTSSpeakingRef.current = false
        isAiSpeakingRef.current = false
        setIsAiSpeaking(false)

        if (currentTtsAudioRef.current) {
            currentTtsAudioRef.current.onended = null
            currentTtsAudioRef.current.onerror = null
            currentTtsAudioRef.current.pause()
            currentTtsAudioRef.current.currentTime = 0
            currentTtsAudioRef.current = null
        }

        if (currentTtsUrlRef.current) {
            URL.revokeObjectURL(currentTtsUrlRef.current)
            currentTtsUrlRef.current = null
        }

        if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
            window.speechSynthesis.cancel()
        }
        browserTtsUtteranceRef.current = null
        browserTtsActiveRef.current = false
    }

    const playBrowserTts = (text: string) => {
        const normalized = text.trim()
        if (!normalized || typeof window === 'undefined' || !('speechSynthesis' in window)) {
            stopCurrentTts()
            return
        }
        if (currentTtsAudioRef.current || ttsAudioQueueRef.current.length > 0) {
            return
        }

        window.speechSynthesis.cancel()

        const utterance = new SpeechSynthesisUtterance(normalized)
        utterance.lang = 'zh-CN'
        utterance.rate = 1
        browserTtsUtteranceRef.current = utterance
        browserTtsActiveRef.current = true
        isTTSSpeakingRef.current = true
        isAiSpeakingRef.current = true
        setIsAiSpeaking(true)

        utterance.onend = () => {
            browserTtsUtteranceRef.current = null
            browserTtsActiveRef.current = false
            pendingTtsTextRef.current = ''
            isTTSSpeakingRef.current = false
            isAiSpeakingRef.current = false
            setIsAiSpeaking(false)
            resumeAudioRecordingAfterTts()
        }
        utterance.onerror = (error) => {
            const reason = (error as any)?.error || ''
            // 当服务端音频抢占时，浏览器合成会收到 canceled/interrupted，这属于正常现象。
            if (reason === 'canceled' || reason === 'interrupted') {
                return
            }
            console.error('[TTS] 浏览器播报失败:', error)
            stopCurrentTts()
        }

        console.warn('[TTS] 切换到浏览器语音播报')
        window.speechSynthesis.speak(utterance)
    }

    const stopBrowserSpeechRecognition = (abort = false) => {
        clearBrowserAsrFallbackTimer()
        browserAsrStopRequestedRef.current = true
        browserAsrActiveRef.current = false
        browserAsrInterimTextRef.current = ''

        const recognition = browserAsrRecognitionRef.current
        if (!recognition) {
            return
        }

        try {
            if (abort) {
                recognition.abort()
            } else {
                recognition.stop()
            }
        } catch (error) {
            console.warn('[ASR] 浏览器识别停止异常:', error)
        }
    }

    const startBrowserSpeechRecognition = () => {
        if (
            typeof window === 'undefined'
            || !interviewStartedRef.current
            || !isRecordingRef.current
            || isAiSpeakingRef.current
            || isAnswerAsrLocked()
            || (isServerAsrAvailableRef.current && Date.now() < serverAsrMuteUntilRef.current)
        ) {
            return
        }
        if (browserAsrActiveRef.current) {
            return
        }

        const RecognitionCtor = getSpeechRecognitionCtor()
        if (!RecognitionCtor) {
            return
        }

        let recognition = browserAsrRecognitionRef.current
        if (!recognition) {
            recognition = new RecognitionCtor()
            recognition.continuous = true
            recognition.interimResults = true
            recognition.lang = 'zh-CN'

            recognition.onstart = () => {
                browserAsrActiveRef.current = true
                browserAsrStopRequestedRef.current = false
                asrChannelRef.current = 'browser'
                console.warn('[ASR] 已切换到浏览器语音识别')
            }
            recognition.onresult = (event: SpeechRecognitionEventLike) => {
                let nextFinal = browserAsrFinalTextRef.current
                let nextInterim = ''

                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const result = event.results[i]
                    const transcript = result?.[0]?.transcript?.trim() || ''
                    if (!transcript) {
                        continue
                    }
                    if (result.isFinal) {
                        nextFinal = mergeTranscriptWithDedup(nextFinal, transcript)
                    } else {
                        nextInterim = mergeTranscriptWithDedup(nextInterim, transcript)
                    }
                }

                browserAsrFinalTextRef.current = nextFinal
                browserAsrInterimTextRef.current = nextInterim
                const mergedText = mergeTranscriptWithDedup(nextFinal, nextInterim)
                if (!mergedText) {
                    return
                }

                setUserAnswer(mergedText)
                setAnswerSessionStatus(nextInterim ? 'recording' : 'paused_short')
            }
            recognition.onerror = (event: SpeechRecognitionErrorEventLike) => {
                console.error('[ASR] 浏览器识别失败:', event.error, event.message || '')
                browserAsrActiveRef.current = false
                if (event.error !== 'aborted') {
                    const fatalBrowserAsrErrors = new Set([
                        'network',
                        'not-allowed',
                        'service-not-allowed',
                        'audio-capture',
                    ])
                    const fallbackMessage = event.error === 'network'
                        ? '浏览器语音识别网络不可达，请使用文字回答。'
                        : '浏览器语音识别不可用，请改用文字回答。'
                    if (fatalBrowserAsrErrors.has(event.error)) {
                        browserAsrStopRequestedRef.current = true
                        setBrowserAsrAvailability(false, fallbackMessage)
                        if (!isServerAsrAvailableRef.current) {
                            stopAudioRecording()
                        }
                    } else {
                        setAsrStatusMessage(fallbackMessage)
                    }
                }
            }
            recognition.onend = () => {
                browserAsrActiveRef.current = false
                if (
                    !browserAsrStopRequestedRef.current
                    && interviewStartedRef.current
                    && isRecordingRef.current
                    && !isAiSpeakingRef.current
                    && (!isServerAsrAvailableRef.current || Date.now() >= serverAsrMuteUntilRef.current)
                ) {
                    setTimeout(() => {
                        startBrowserSpeechRecognition()
                    }, 150)
                }
            }

            browserAsrRecognitionRef.current = recognition
        }

        try {
            recognition.start()
        } catch (error) {
            console.warn('[ASR] 浏览器识别启动异常:', error)
        }
    }

    const scheduleBrowserAsrFallback = (delayOverrideMs?: number) => {
        clearBrowserAsrFallbackTimer()
        if (
            !isBrowserAsrSupportedRef.current
            || !interviewStartedRef.current
            || !isRecordingRef.current
            || isAiSpeakingRef.current
            || isAnswerAsrLocked()
        ) {
            return
        }
        if (isServerAsrAvailableRef.current && !ENABLE_BROWSER_ASR_STALL_FALLBACK) {
            return
        }

        const delay = typeof delayOverrideMs === 'number'
            ? delayOverrideMs
            : (isServerAsrAvailableRef.current ? SERVER_ASR_FALLBACK_DELAY_MS : 180)
        browserAsrFallbackTimerRef.current = setTimeout(() => {
            if (!interviewStartedRef.current || !isRecordingRef.current || isAiSpeakingRef.current || isAnswerAsrLocked()) {
                return
            }
            const now = Date.now()
            const noServerTranscript = now - lastServerTranscriptAtRef.current > SERVER_ASR_STALL_WINDOW_MS
            const mutualExclusionPassed = now >= serverAsrMuteUntilRef.current
            const shouldFallbackToBrowser = !isServerAsrAvailableRef.current || (
                ENABLE_BROWSER_ASR_STALL_FALLBACK
                && noServerTranscript
                && mutualExclusionPassed
            )
            if (shouldFallbackToBrowser) {
                if (
                    socketRef.current
                    && isServerAsrAvailableRef.current
                    && asrChannelRef.current === 'server'
                    && activeSpeechEpochRef.current > 0
                    && sessionIdRef.current
                ) {
                    socketRef.current.emit('speech_end', {
                        session_id: sessionIdRef.current,
                        turn_id: currentTurnIdRef.current,
                        speech_epoch: activeSpeechEpochRef.current
                    })
                    activeSpeechEpochRef.current = 0
                }
                asrChannelRef.current = 'browser'
                startBrowserSpeechRecognition()
                return
            }

            if (
                isServerAsrAvailableRef.current
                && speechActiveRef.current
                && asrChannelRef.current === 'server'
                && !browserAsrActiveRef.current
            ) {
                scheduleBrowserAsrFallback(SERVER_ASR_RECHECK_DELAY_MS)
            }
        }, delay)
    }

    useEffect(() => {
        interviewStartedRef.current = interviewStarted
    }, [interviewStarted])

    useEffect(() => {
        if (!interviewStarted) {
            return
        }
        const interval = setInterval(() => {
            setSessionElapsed(prev => prev + 1)
        }, 1000)
        return () => clearInterval(interval)
    }, [interviewStarted])

    useEffect(() => {
        isAiSpeakingRef.current = isAiSpeaking
    }, [isAiSpeaking])

    useEffect(() => {
        isRecordingRef.current = isRecording
    }, [isRecording])

    useEffect(() => {
        userAnswerRef.current = userAnswer
    }, [userAnswer])

    useEffect(() => {
        answerSessionStatusRef.current = answerSessionStatus
    }, [answerSessionStatus])

    useEffect(() => {
        const supported = Boolean(getSpeechRecognitionCtor())
        setBrowserAsrAvailability(supported)
    }, [])

    useEffect(() => {
        const chatContainer = chatScrollContainerRef.current
        if (!chatContainer) {
            return
        }

        chatContainer.scrollTo({
            top: chatContainer.scrollHeight,
            behavior: 'smooth'
        })
    }, [chatMessages])

    useEffect(() => {
        if (!videoRef.current || !cameraStreamRef.current) {
            return
        }

        if (videoRef.current.srcObject !== cameraStreamRef.current) {
            videoRef.current.srcObject = cameraStreamRef.current
        }

        const playPromise = videoRef.current.play()
        if (playPromise && typeof playPromise.catch === 'function') {
            playPromise.catch((error) => {
                console.warn('Camera preview play interrupted:', error)
            })
        }
    }, [interviewStarted])

    useEffect(() => {
        // 从 sessionStorage 读取面试配置
        const savedConfig = sessionStorage.getItem('interview_config')
        if (savedConfig) {
            const config = JSON.parse(savedConfig)
            const roundMap: Record<string, string> = {
                'technical': '技术基础面',
                'project': '项目深度面',
                'system_design': '系统设计面',
                'hr': 'HR 综合面'
            }
            const selectedQuestion = config?.selectedQuestion && typeof config.selectedQuestion === 'object'
                ? {
                    id: String(config.selectedQuestion.id || '').trim(),
                    question: String(config.selectedQuestion.question || '').trim(),
                    category: String(config.selectedQuestion.category || '').trim(),
                    round_type: String(config.selectedQuestion.round_type || '').trim(),
                    position: String(config.selectedQuestion.position || '').trim(),
                    difficulty: String(config.selectedQuestion.difficulty || '').trim(),
                }
                : null
            const autoEndMinRaw = Number(config?.auto_end_min_questions)
            const autoEndMaxRaw = Number(config?.auto_end_max_questions)
            const autoEndMin = Number.isFinite(autoEndMinRaw) && autoEndMinRaw > 0 ? autoEndMinRaw : undefined
            const autoEndMax = Number.isFinite(autoEndMaxRaw) && autoEndMaxRaw > 0 ? autoEndMaxRaw : undefined
            setInterviewConfig({
                round: config.round || 'technical',
                roundName: roundMap[config.round] || '技术基础面',
                position: config.position || 'java_backend',
                difficulty: config.difficulty || 'medium',
                selectedQuestion: selectedQuestion && selectedQuestion.question ? selectedQuestion : null,
                trainingTaskId: String(config?.trainingTaskId || '').trim(),
                trainingMode: String(config?.trainingMode || '').trim(),
                auto_end_min_questions: autoEndMin,
                auto_end_max_questions: autoEndMax,
            })
        }

        initCamera()
        initSocket()
        initAudioRecording()

        return () => {
            clearLlmTimeout()
            clearPendingCommit()
            stopCurrentTts()
            void stopVideoRecording(sessionIdRef.current, false)
            cleanupAudioRecording()
            stopBrowserSpeechRecognition(true)
            stopCamera()
            const activeSocket = socketRef.current
            if (activeSocket) {
                if (sessionIdRef.current) {
                    activeSocket.emit('session_end', { session_id: sessionIdRef.current })
                }
                activeSocket.disconnect()
                socketRef.current = null
            }
        }
    }, [])

    const initCamera = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: 'user',
                },
            })

            cameraStreamRef.current = stream
            setCameraReady(true)

            if (videoRef.current) {
                videoRef.current.srcObject = stream
                const playPromise = videoRef.current.play()
                if (playPromise && typeof playPromise.catch === 'function') {
                    playPromise.catch((error) => {
                        console.warn('Initial camera preview play interrupted:', error)
                    })
                }
            }
        } catch (error: any) {
            console.error('Camera error:', error)
            const msg =
                error?.name === 'NotAllowedError'
                    ? '摄像头/麦克风权限被拒绝，请在浏览器设置中允许访问。'
                    : error?.name === 'NotFoundError'
                    ? '未检测到摄像头设备，请确认摄像头已连接。'
                    : error?.name === 'NotReadableError'
                    ? '摄像头被其他应用占用，请关闭其他使用摄像头的程序后重试。'
                    : `摄像头启动失败：${error?.message || '未知错误'}`;
            alert(msg)
            router.push('/dashboard')
        }
    }

    const stopCamera = () => {
        if (videoRef.current) {
            videoRef.current.srcObject = null
        }

        if (cameraStreamRef.current) {
            cameraStreamRef.current.getTracks().forEach(track => track.stop())
            cameraStreamRef.current = null
        }

        setCameraReady(false)
    }

    const speakText = (text: string) => {
        if (!text || !text.trim()) return

        pendingTtsTextRef.current = text.trim()
        receivedServerChunkForCurrentSpeakRef.current = false
        ttsDoneSignaledRef.current = false
        setIsAiSpeaking(true)
        isAiSpeakingRef.current = true
        isTTSSpeakingRef.current = true
    }

    const playNextTtsChunk = () => {
        if (currentTtsAudioRef.current || ttsAudioQueueRef.current.length === 0) {
            return
        }

        const item = ttsAudioQueueRef.current.shift()
        if (!item) return

        try {
            console.log('[TTS] 开始播放音频')

            const binaryString = atob(item.audio)
            const len = binaryString.length
            const bytes = new Uint8Array(len)
            for (let i = 0; i < len; i++) {
                bytes[i] = binaryString.charCodeAt(i)
            }

            const blob = new Blob([bytes], { type: item.mimeType || 'audio/mpeg' })
            const url = URL.createObjectURL(blob)
            currentTtsUrlRef.current = url

            const audio = new Audio()
            audio.src = url
            currentTtsAudioRef.current = audio
            audio.onended = () => {
                if (currentTtsAudioRef.current !== audio) return
                console.log('[TTS] 播放完成')
                if (currentTtsUrlRef.current === url) {
                    URL.revokeObjectURL(currentTtsUrlRef.current)
                    currentTtsUrlRef.current = null
                }
                currentTtsAudioRef.current = null
                if (ttsAudioQueueRef.current.length === 0) {
                    if (ttsDoneSignaledRef.current) {
                        finalizeCurrentTtsPlayback()
                    } else {
                        console.log('[TTS] 播放队列已空，等待服务端完成信号')
                    }
                }
                playNextTtsChunk()
            }
            audio.onerror = (error) => {
                if (currentTtsAudioRef.current !== audio) return
                console.error('[TTS] 播放错误:', error)
                stopCurrentTts()
            }

            if (browserTtsActiveRef.current && typeof window !== 'undefined' && 'speechSynthesis' in window) {
                window.speechSynthesis.cancel()
                browserTtsActiveRef.current = false
            }

            audio.play().catch((err) => {
                if (currentTtsAudioRef.current !== audio) return
                if ((err as any)?.name === 'AbortError') {
                    // 可能被 stop/pause 或新音频抢占，不作为失败处理。
                    return
                }
                console.error('[TTS] 播放失败:', err)
                stopCurrentTts()
            })
        } catch (error) {
            console.error('[TTS] 播放异常:', error)
            stopCurrentTts()
        }
    }

    const initAudioRecording = async () => {
        if (typeof window === 'undefined') return
        if (audioWorkletNodeRef.current || audioContextRef.current) return

        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: ASR_CAPTURE_CONSTRAINTS
            })
            microphoneStreamRef.current = stream

            const audioContext = new AudioContext({ sampleRate: 16000 })
            const source = audioContext.createMediaStreamSource(stream)
            audioContextRef.current = audioContext
            console.log('[ASR] AudioContext sampleRate:', audioContext.sampleRate)

            // 使用 AudioWorklet 处理音频
            await audioContext.audioWorklet.addModule('/audio-processor.js')
            const workletNode = new AudioWorkletNode(audioContext, 'audio-processor', {
                processorOptions: { sampleRate: 16000 }
            })

            workletNode.port.onmessage = (event) => {
                if (event?.data?.type === 'meta') {
                    console.log('[ASR] Worklet meta:', event.data)
                    return
                }

                if (
                    !socketRef.current
                    || !isRecordingRef.current
                    || !interviewStartedRef.current
                    || !sessionIdRef.current
                    || isAnswerAsrLocked()
                ) {
                    return
                }
                if (isAiSpeakingRef.current) {
                    consecutiveSpeechFramesRef.current = 0
                    clearSpeechPrebuffer()
                    stopBrowserSpeechRecognition()
                    return
                }

                if (event?.data?.type === 'audio-chunk' && event.data.audio instanceof ArrayBuffer) {
                    const pcmData = (event.data.audio as ArrayBuffer).slice(0)
                    const rms = Number(event.data.rms || 0)
                    const now = performance.now()
                    if (!speechActiveRef.current) {
                        noiseFloorRef.current = clamp(
                            noiseFloorRef.current * 0.92 + rms * 0.08,
                            ASR_NOISE_FLOOR_MIN,
                            ASR_NOISE_FLOOR_MAX
                        )
                    }

                    const activationThreshold = clamp(
                        noiseFloorRef.current * ASR_ACTIVATION_MULTIPLIER,
                        ASR_ACTIVATION_MIN,
                        ASR_ACTIVATION_MAX
                    )
                    const fastStartActivationThreshold = clamp(
                        noiseFloorRef.current * ASR_FAST_START_ACTIVATION_MULTIPLIER,
                        ASR_FAST_START_ACTIVATION_MIN,
                        ASR_ACTIVATION_MAX
                    )
                    const holdThreshold = clamp(
                        noiseFloorRef.current * ASR_HOLD_MULTIPLIER,
                        ASR_HOLD_MIN,
                        ASR_HOLD_MAX
                    )
                    const isFastStartWindow = !speechActiveRef.current
                        && fastStartUntilRef.current > 0
                        && now <= fastStartUntilRef.current
                    const startThreshold = isFastStartWindow
                        ? Math.min(activationThreshold, fastStartActivationThreshold)
                        : activationThreshold
                    const speechThreshold = speechActiveRef.current ? holdThreshold : startThreshold
                    const isSpeechChunk = rms >= speechThreshold
                    const requiredSpeechFrames = isFastStartWindow
                        ? (rms >= startThreshold * ASR_FAST_START_STRONG_MULTIPLIER ? 1 : 2)
                        : (rms >= activationThreshold * ASR_STRONG_SPEECH_MULTIPLIER ? 2 : 3)
                    enqueueSpeechPrebuffer(pcmData)

                    if (isSpeechChunk) {
                        consecutiveSpeechFramesRef.current += 1
                        lastSpeechAtRef.current = now
                        if (!speechActiveRef.current && consecutiveSpeechFramesRef.current >= requiredSpeechFrames) {
                            speechActiveRef.current = true
                            clearPendingCommit()
                            browserAsrFinalTextRef.current = ''
                            browserAsrInterimTextRef.current = ''
                            lastServerTranscriptAtRef.current = Date.now()
                            clientSpeechEpochRef.current += 1
                            activeSpeechEpochRef.current = clientSpeechEpochRef.current
                            const prebufferChunks = [...speechPrebufferRef.current]
                            if (isServerAsrAvailableRef.current) {
                                asrChannelRef.current = 'server'
                                const prebufferMs = prebufferChunks.length * ASR_AUDIO_CHUNK_MS
                                pushLocalAsrDebugEvent('client_speech_start_emit', {
                                    speech_epoch: activeSpeechEpochRef.current,
                                    details: `rms=${rms.toFixed(4)} threshold=${speechThreshold.toFixed(4)} channel=server prebuffer_chunks=${prebufferChunks.length} prebuffer_ms=${prebufferMs}`,
                                })
                                socketRef.current.emit('speech_start', {
                                    session_id: sessionIdRef.current,
                                    turn_id: currentTurnIdRef.current,
                                    speech_epoch: activeSpeechEpochRef.current
                                })
                                for (const chunk of prebufferChunks) {
                                    socketRef.current.emit('audio_chunk', {
                                        session_id: sessionIdRef.current,
                                        turn_id: currentTurnIdRef.current,
                                        audio: arrayBufferToBase64(chunk)
                                    })
                                }
                            } else {
                                asrChannelRef.current = 'browser'
                                startBrowserSpeechRecognition()
                            }
                            scheduleBrowserAsrFallback()
                            clearSpeechPrebuffer()
                            return
                        }
                    } else {
                        consecutiveSpeechFramesRef.current = 0
                    }

                    const adaptiveSilenceMs = clamp(
                        BASE_SILENCE_MS
                        + (browserAsrActiveRef.current ? BROWSER_SILENCE_BONUS_MS : 0)
                        + (noiseFloorRef.current > 0.012 ? NOISY_ENV_SILENCE_BONUS_MS : 0),
                        MIN_ADAPTIVE_SILENCE_MS,
                        MAX_ADAPTIVE_SILENCE_MS
                    )
                    if (speechActiveRef.current && now - lastSpeechAtRef.current >= adaptiveSilenceMs) {
                        speechActiveRef.current = false
                        if (isServerAsrAvailableRef.current && asrChannelRef.current === 'server' && activeSpeechEpochRef.current > 0) {
                            pushLocalAsrDebugEvent('client_speech_end_emit', {
                                speech_epoch: activeSpeechEpochRef.current,
                                details: `silence_ms=${Math.round(now - lastSpeechAtRef.current)} channel=server`,
                            })
                            socketRef.current.emit('speech_end', {
                                session_id: sessionIdRef.current,
                                turn_id: currentTurnIdRef.current,
                                speech_epoch: activeSpeechEpochRef.current
                            })
                        }
                        activeSpeechEpochRef.current = 0
                        asrChannelRef.current = 'none'
                        stopBrowserSpeechRecognition()
                        clearSpeechPrebuffer()
                    }

                    // 只在检测到用户说话时上传音频，避免长时间静音导致服务端 ASR 会话超时。
                    const shouldSendAudio = speechActiveRef.current && isServerAsrAvailableRef.current && asrChannelRef.current === 'server'
                    if (!shouldSendAudio) {
                        return
                    }

                    const base64Audio = arrayBufferToBase64(pcmData)
                    socketRef.current.emit('audio_chunk', {
                        session_id: sessionIdRef.current,
                        turn_id: currentTurnIdRef.current,
                        audio: base64Audio
                    })
                }
            }

            source.connect(workletNode)
            workletNode.connect(audioContext.destination)
            audioWorkletNodeRef.current = workletNode

            setIsVoiceSupported(true)
            console.log('[ASR] 音频录制初始化完成')
        } catch (error) {
            console.error('[ASR] 音频录制初始化失败:', error)
            setIsVoiceSupported(false)
        }
    }

    const arrayBufferToBase64 = (buffer: ArrayBuffer): string => {
        const bytes = new Uint8Array(buffer)
        let binary = ''
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i])
        }
        return btoa(binary)
    }

    const startAudioRecording = async () => {
        if (!isServerAsrAvailableRef.current && !isBrowserAsrSupportedRef.current) {
            console.warn('[ASR] 服务不可用，且浏览器语音识别不可用，跳过录音启动')
            return
        }
        if (isAnswerAsrLocked()) {
            console.warn('[ASR] 当前回答已锁定，跳过录音启动')
            return
        }
        if (isAiSpeakingRef.current) {
            return
        }
        if (!audioWorkletNodeRef.current) {
            console.warn('[ASR] audioWorkletNodeRef 为空')
            return
        }
        if (!interviewStartedRef.current) {
            console.warn('[ASR] interviewStartedRef 为 false')
            return
        }

        if (audioContextRef.current?.state === 'suspended') {
            await audioContextRef.current.resume()
        }

        isRecordingRef.current = true
        asrChannelRef.current = 'none'
        setIsRecording(true)
        setIsListening(true)
        pushLocalAsrDebugEvent('client_recording_started', {
            details: `server_asr=${String(isServerAsrAvailableRef.current)} browser_asr=${String(isBrowserAsrSupportedRef.current)}`,
        })
        console.log('[ASR] 开始录音')
    }

    const resumeAudioRecordingAfterTts = () => {
        if (
            !interviewStartedRef.current
            || isAiSpeakingRef.current
            || isRecordingRef.current
            || isAnswerAsrLocked()
            || ['finalizing', 'finalized'].includes(answerSessionStatusRef.current)
        ) {
            return
        }
        fastStartUntilRef.current = performance.now() + ASR_FAST_START_WINDOW_MS
        void startAudioRecording()
    }

    const stopAudioRecording = () => {
        if (!isRecordingRef.current && !speechActiveRef.current && !pendingCommitTimerRef.current) {
            return
        }
        clearPendingCommit()
        clearBrowserAsrFallbackTimer()
        stopBrowserSpeechRecognition()

        if (
            socketRef.current
            && sessionIdRef.current
            && isServerAsrAvailableRef.current
            && asrChannelRef.current === 'server'
            && activeSpeechEpochRef.current > 0
        ) {
            pushLocalAsrDebugEvent('client_speech_end_emit', {
                speech_epoch: activeSpeechEpochRef.current,
                details: 'stopAudioRecording channel=server',
            })
            socketRef.current.emit('speech_end', {
                session_id: sessionIdRef.current,
                turn_id: currentTurnIdRef.current,
                speech_epoch: activeSpeechEpochRef.current
            })
        }

        speechActiveRef.current = false
        consecutiveSpeechFramesRef.current = 0
        activeSpeechEpochRef.current = 0
        fastStartUntilRef.current = 0
        asrChannelRef.current = 'none'
        clearSpeechPrebuffer()
        isRecordingRef.current = false
        setIsRecording(false)
        setIsListening(false)
        pushLocalAsrDebugEvent('client_recording_stopped')
        console.log('[ASR] 停止录音')
    }

    const cleanupAudioRecording = () => {
        stopAudioRecording()
        if (audioWorkletNodeRef.current) {
            audioWorkletNodeRef.current.disconnect()
            audioWorkletNodeRef.current = null
        }
        if (audioContextRef.current) {
            audioContextRef.current.close()
            audioContextRef.current = null
        }
        if (microphoneStreamRef.current) {
            microphoneStreamRef.current.getTracks().forEach(track => track.stop())
            microphoneStreamRef.current = null
        }
    }

    const initSocket = async () => {
        const socketClient = SocketClient.getInstance()

        try {
            await socketClient.connect()
            setSocket(socketClient)
            socketRef.current = socketClient

            // 避免开发模式下重复注册同名事件监听器
            socketClient.off('orchestrator_state')
            socketClient.off('dialog_reply')
            socketClient.off('answer_session_update')
            socketClient.off('speech_metrics_realtime')
            socketClient.off('asr_partial')
            socketClient.off('asr_final')
            socketClient.off('asr_debug')
            socketClient.off('tts_chunk')
            socketClient.off('tts_done')
            socketClient.off('tts_stop')
            socketClient.off('session_control_notice')
            socketClient.off('pipeline_error')
            socketClient.off('error')
            socketClient.off('interview_should_end')
            socketClient.off('interview_ended')

            socketClient.on('orchestrator_state', (data: any) => {
                if (sessionIdRef.current && data?.session_id && data.session_id !== sessionIdRef.current) {
                    return
                }
                if (data?.session_id) {
                    sessionIdRef.current = data.session_id
                }
                if (data?.turn_id) {
                    currentTurnIdRef.current = data.turn_id
                }
                if (typeof data?.interrupt_epoch === 'number') {
                    interruptEpochRef.current = data.interrupt_epoch
                }
                if (typeof data?.asr_locked === 'boolean') {
                    asrLockedRef.current = data.asr_locked
                    if (data.asr_locked) {
                        stopAudioRecording()
                    }
                }
                activeTtsJobIdRef.current = data?.active_tts_job_id || ''
                if (typeof data?.asr_available === 'boolean') {
                    const wasServerAsrAvailable = isServerAsrAvailableRef.current
                    setServerAsrAvailability(data.asr_available, data?.asr_error || '')
                    if (wasServerAsrAvailable && !data.asr_available) {
                        speechActiveRef.current = false
                        clearPendingCommit()
                        clearSpeechPrebuffer()
                        if (!isBrowserAsrSupportedRef.current) {
                            stopAudioRecording()
                        }
                    }
                }

                const mode = data?.mode || 'idle'
                setIsProcessing(mode === 'thinking')
                setIsListening(mode === 'listening' || mode === 'interrupted')
                if (mode === 'speaking') {
                    setIsListening(false)
                    stopAudioRecording()
                } else if (
                    mode === 'listening'
                    && interviewStartedRef.current
                    && (isServerAsrAvailableRef.current || isBrowserAsrSupportedRef.current)
                    && !asrLockedRef.current
                    && !['finalizing', 'finalized'].includes(answerSessionStatusRef.current)
                    && !isRecordingRef.current
                ) {
                    startAudioRecording()
                }
                if (mode === 'ended') {
                    void stopVideoRecording(sessionIdRef.current, true)
                    interviewStartedRef.current = false
                    setInterviewStarted(false)
                    stopCurrentTts()
                    stopAudioRecording()
                }
            })

            socketClient.on('dialog_reply', (data: any) => {
                console.log('Dialog reply:', data)
                clearLlmTimeout()
                if (!data?.display_text || !data?.session_id) return
                if (!interviewStartedRef.current) return
                if (!sessionIdRef.current || data.session_id !== sessionIdRef.current) return
                if (typeof data?.interrupt_epoch === 'number' && data.interrupt_epoch < interruptEpochRef.current) return

                if (data.session_id) {
                    sessionIdRef.current = data.session_id
                }
                if (data.turn_id) {
                    currentTurnIdRef.current = data.turn_id
                }
                asrLockedRef.current = false
                resetAnswerSessionUi()

                setCurrentQuestion(String(data?.followup_decision?.coach_next_question || data.display_text || ''))
                setUserAnswer('')
                speakText(data.spoken_text || data.display_text)
                setChatMessages(prev => [...prev, {
                    role: 'interviewer',
                    content: data.display_text,
                    timestamp: new Date().toLocaleTimeString()
                }])
                setIsProcessing(false)
            })

            socketClient.on('answer_session_update', (data: any) => {
                if (!data?.session_id || data.session_id !== sessionIdRef.current) return
                if (data?.turn_id && currentTurnIdRef.current && data.turn_id !== currentTurnIdRef.current) return
                if (typeof data?.interrupt_epoch === 'number' && data.interrupt_epoch < interruptEpochRef.current) return

                const answerSessionId = data?.answer_session_id || ''
                if (answerSessionId) {
                    answerSessionIdRef.current = answerSessionId
                }

                const allowServerTranscript = asrChannelRef.current !== 'browser'
                if ((data?.display_text || data?.final_text || data?.live_text || data?.merged_text_draft) && allowServerTranscript) {
                    markServerTranscriptActive()
                    if (browserAsrActiveRef.current) {
                        stopBrowserSpeechRecognition()
                    }
                }

                setAnswerSessionStatus(data?.status || 'idle')
                setFinalMetricsReady(Boolean(data?.final_metrics_ready))
                if (data?.speech_metrics_realtime) {
                    setSpeechRealtimeMetrics({
                        is_speaking: Boolean(data.speech_metrics_realtime.is_speaking),
                        rough_wpm: Number(data.speech_metrics_realtime.rough_wpm || 0),
                        silence_ms: Number(data.speech_metrics_realtime.silence_ms || 0),
                        segment_index: Number(data.speech_metrics_realtime.segment_index || 0),
                    })
                }

                const displayText = data?.display_text || data?.final_text || data?.live_text || data?.merged_text_draft || ''
                if (typeof displayText === 'string' && asrChannelRef.current !== 'browser') {
                    setUserAnswer(displayText)
                }

                if (['finalizing', 'finalized'].includes(data?.status || '')) {
                    asrLockedRef.current = true
                    stopAudioRecording()
                }

                if (data?.committed && answerSessionId && !committedAnswerSessionIdsRef.current.has(answerSessionId)) {
                    committedAnswerSessionIdsRef.current.add(answerSessionId)
                    appendCandidateMessage(displayText)
                }
            })

            socketClient.on('speech_metrics_realtime', (data: any) => {
                if (!data?.session_id || data.session_id !== sessionIdRef.current) return
                if (data?.turn_id && currentTurnIdRef.current && data.turn_id !== currentTurnIdRef.current) return
                if (typeof data?.interrupt_epoch === 'number' && data.interrupt_epoch < interruptEpochRef.current) return
                setSpeechRealtimeMetrics({
                    is_speaking: Boolean(data?.is_speaking),
                    rough_wpm: Number(data?.rough_wpm || 0),
                    silence_ms: Number(data?.silence_ms || 0),
                    segment_index: Number(data?.segment_index || 0),
                })
            })

            socketClient.on('asr_partial', (data: any) => {
                if (!data?.session_id || data.session_id !== sessionIdRef.current) return
                if (data?.turn_id && currentTurnIdRef.current && data.turn_id !== currentTurnIdRef.current) return
                if (typeof data?.interrupt_epoch === 'number' && data.interrupt_epoch < interruptEpochRef.current) return
                if (asrChannelRef.current !== 'browser') {
                    markServerTranscriptActive()
                }
                if (browserAsrActiveRef.current && asrChannelRef.current !== 'browser') {
                    stopBrowserSpeechRecognition()
                }
                const partialDisplayText = data?.full_text || data?.text || ''
                if (!answerSessionIdRef.current && partialDisplayText && asrChannelRef.current !== 'browser') {
                    setUserAnswer(normalizeTranscript(partialDisplayText))
                }
            })

            socketClient.on('asr_final', (data: any) => {
                if (!data?.session_id || data.session_id !== sessionIdRef.current) return
                if (data?.turn_id && currentTurnIdRef.current && data.turn_id !== currentTurnIdRef.current) return
                if (typeof data?.interrupt_epoch === 'number' && data.interrupt_epoch < interruptEpochRef.current) return
                if (asrChannelRef.current !== 'browser') {
                    markServerTranscriptActive()
                }
                if (browserAsrActiveRef.current && asrChannelRef.current !== 'browser') {
                    stopBrowserSpeechRecognition()
                }
                const finalDisplayText = data?.full_text || data?.preview_text || data?.text || ''
                if (!answerSessionIdRef.current && finalDisplayText && asrChannelRef.current !== 'browser') {
                    setUserAnswer(normalizeTranscript(finalDisplayText))
                }
            })

            socketClient.on('asr_debug', (data: any) => {
                if (!ASR_DEBUG_PANEL_ENABLED) return
                if (!data?.session_id || data.session_id !== sessionIdRef.current) return
                if (data?.turn_id && currentTurnIdRef.current && data.turn_id !== currentTurnIdRef.current) return
                if (typeof data?.interrupt_epoch === 'number' && data.interrupt_epoch < interruptEpochRef.current) return

                const item: AsrDebugEvent = {
                    event: String(data?.event || '').trim() || 'asr_event',
                    level: String(data?.level || 'info').trim() || 'info',
                    timestamp: Number(data?.timestamp || Date.now() / 1000),
                    session_id: data?.session_id || '',
                    turn_id: data?.turn_id || '',
                    source: data?.source || '',
                    reason: data?.reason || '',
                    reason_detail: data?.reason_detail || '',
                    asr_generation: data?.asr_generation ?? '',
                    speech_epoch: data?.speech_epoch ?? '',
                    details: data?.details || '',
                    partial_preview: data?.partial_preview || '',
                    final_preview: data?.final_preview || '',
                    segment_preview: data?.segment_preview || '',
                    answer_preview: data?.answer_preview || '',
                    text_snapshot: data?.text_snapshot || '',
                }

                setAsrDebugEvents((prev) => {
                    const next = [...prev, item]
                    if (next.length <= ASR_DEBUG_MAX_ITEMS) {
                        return next
                    }
                    return next.slice(next.length - ASR_DEBUG_MAX_ITEMS)
                })
            })

            socketClient.on('tts_chunk', (data: any) => {
                if (!data?.audio || !data?.session_id) return
                if (data.session_id !== sessionIdRef.current) return
                if (typeof data?.interrupt_epoch === 'number' && data.interrupt_epoch < interruptEpochRef.current) return
                if (activeTtsJobIdRef.current && data?.job_id && data.job_id !== activeTtsJobIdRef.current) return

                receivedServerChunkForCurrentSpeakRef.current = true

                // 服务端音频到达后，优先使用服务端流，抢占浏览器播报。
                if (browserTtsActiveRef.current && typeof window !== 'undefined' && 'speechSynthesis' in window) {
                    window.speechSynthesis.cancel()
                    browserTtsUtteranceRef.current = null
                    browserTtsActiveRef.current = false
                }
                ttsAudioQueueRef.current.push({
                    audio: data.audio,
                    jobId: data.job_id || '',
                    turnId: data.turn_id || '',
                    mimeType: data.mime_type || 'audio/mpeg',
                    provider: data.provider || ''
                })
                if (data?.provider) {
                    console.log('[TTS] 收到服务端音频:', data.provider, data.mime_type || 'audio/mpeg')
                }
                playNextTtsChunk()
            })

            socketClient.on('tts_done', (data: any) => {
                if (!data?.session_id) return
                if (data.session_id !== sessionIdRef.current) return
                if (typeof data?.interrupt_epoch === 'number' && data.interrupt_epoch < interruptEpochRef.current) return
                if (activeTtsJobIdRef.current && data?.job_id && data.job_id !== activeTtsJobIdRef.current) return

                ttsDoneSignaledRef.current = true
                if (!currentTtsAudioRef.current && ttsAudioQueueRef.current.length === 0) {
                    finalizeCurrentTtsPlayback()
                }
            })

            socketClient.on('tts_stop', (data: any) => {
                console.log('[TTS] 收到停止指令:', data)
                if (typeof data?.interrupt_epoch === 'number') {
                    interruptEpochRef.current = data.interrupt_epoch
                }
                activeTtsJobIdRef.current = ''
                stopCurrentTts()
            })

            socketClient.on('session_control_notice', (data: any) => {
                if (!data?.display_text) return
                if (data?.session_id && sessionIdRef.current && data.session_id !== sessionIdRef.current) return
                if (typeof data?.interrupt_epoch === 'number' && data.interrupt_epoch < interruptEpochRef.current) return

                const shouldSpeakNotice =
                    Boolean((data?.spoken_text || '').trim())
                    && !isRecordingRef.current
                    && !speechActiveRef.current
                    && !isAiSpeakingRef.current
                    && !isAnswerAsrLocked()
                if (shouldSpeakNotice) {
                    speakText(data.spoken_text)
                }
                setChatMessages(prev => {
                    const lastMessage = prev[prev.length - 1]
                    if (lastMessage?.role === 'interviewer' && lastMessage.content.trim() === String(data.display_text).trim()) {
                        return prev
                    }
                    return [...prev, {
                        role: 'interviewer',
                        content: data.display_text,
                        timestamp: new Date().toLocaleTimeString()
                    }]
                })
            })

            socketClient.on('pipeline_error', (data: any) => {
                if (data?.session_id && sessionIdRef.current && data.session_id !== sessionIdRef.current) return
                const isAsrFallbackError = ['ASR_NOT_READY', 'ASR_START_FAILED', 'ASR_STREAM_ERROR'].includes(data?.code)
                if (isAsrFallbackError) {
                    console.warn('[Pipeline] ASR 已降级为文本模式:', data)
                } else {
                    console.error('[Pipeline] 后端错误:', data)
                }
                clearLlmTimeout()
                setIsProcessing(false)
                setIsEndingInterview(false)
                if (data?.code === 'TTS_SYNTH_FAIL') {
                    const shouldFallbackToBrowser =
                        pendingTtsTextRef.current
                        && !receivedServerChunkForCurrentSpeakRef.current
                        && !currentTtsAudioRef.current
                        && ttsAudioQueueRef.current.length === 0
                    if (shouldFallbackToBrowser) {
                        console.warn('[TTS] 服务端合成失败，切换到浏览器语音兜底')
                        playBrowserTts(pendingTtsTextRef.current)
                    } else {
                        console.warn('[TTS] 服务端已开始输出，禁止浏览器语音兜底以避免重复播报')
                    }
                } else {
                    stopCurrentTts()
                }
                if (isAsrFallbackError) {
                    const wasServerAsrAvailable = isServerAsrAvailableRef.current
                    speechActiveRef.current = false
                    clearPendingCommit()
                    clearSpeechPrebuffer()
                    resetAnswerSessionUi()
                    const fallbackMessage = isBrowserAsrSupportedRef.current
                        ? '服务端 ASR 不可用，已切换到浏览器语音识别。'
                        : '语音识别服务不可用，请改用文字回答。'
                    setServerAsrAvailability(false, data?.details || data?.error || fallbackMessage)
                    if (wasServerAsrAvailable && !isBrowserAsrSupportedRef.current) {
                        stopAudioRecording()
                    } else if (!isRecordingRef.current && interviewStartedRef.current) {
                        startAudioRecording()
                    }
                }
            })

            socketClient.on('error', (data: any) => {
                console.error('[Interview] 后端错误:', data)
                clearLlmTimeout()
                setIsProcessing(false)
            })

            socketClient.on('interview_should_end', (data: any) => {
                if (data?.session_id && sessionIdRef.current && data.session_id !== sessionIdRef.current) return
                if (autoEndingRef.current) return
                if (!sessionIdRef.current) return
                autoEndingRef.current = true
                void (async () => {
                    try {
                        await requestSessionEnd(socketClient, sessionIdRef.current)
                    } catch (error) {
                        autoEndingRef.current = false
                        console.error('[Interview] 自动结束失败:', error)
                    }
                })()
            })

            socketClient.on('interview_ended', (data: any) => {
                if (data?.session_id && sessionIdRef.current && data.session_id !== sessionIdRef.current) return
                console.log('Interview ended:', data)
                const endedSessionId = String(data?.session_id || sessionIdRef.current || '').trim()
                const endedInterviewId = String(data?.interview_id || buildInterviewId(endedSessionId)).trim()
                if (typeof window !== 'undefined') {
                    window.localStorage.setItem(KNOWLEDGE_GRAPH_REFRESH_KEY, `${Date.now()}:${endedInterviewId || endedSessionId}`)
                }
                autoEndingRef.current = false
                setIsEndingInterview(false)
                void stopVideoRecording(endedSessionId, true)
                setCompletedInterviewId(endedInterviewId)
                interviewStartedRef.current = false
                setInterviewStarted(false)
                sessionIdRef.current = ''
                currentTurnIdRef.current = ''
                interruptEpochRef.current = 0
                activeTtsJobIdRef.current = ''
                resetAnswerSessionUi()
                stopAudioRecording()
                setShowCompletionModal(true)
            })
        } catch (error) {
            console.error('Socket connection error:', error)
            alert('Failed to connect to server')
            router.push('/dashboard')
        }
    }

    const startInterviewSession = (socketClient: SocketClient) => {
        socketRef.current = socketClient
        autoEndingRef.current = false
        setShowCompletionModal(false)
        setIsEndingInterview(false)
        clearLlmTimeout()
        clearPendingCommit()
        stopCurrentTts()
        const sessionId = typeof crypto !== 'undefined' && 'randomUUID' in crypto
            ? crypto.randomUUID()
            : `session_${Date.now()}`
        sessionIdRef.current = sessionId
        currentTurnIdRef.current = ''
        interruptEpochRef.current = 0
        activeTtsJobIdRef.current = ''
        clientSpeechEpochRef.current = 0
        activeSpeechEpochRef.current = 0
        speechActiveRef.current = false
        asrChannelRef.current = 'none'
        noiseFloorRef.current = 0.004
        serverAsrMuteUntilRef.current = 0
        clearSpeechPrebuffer()
        setServerAsrAvailability(true)
        resetAnswerSessionUi()
        interviewStartedRef.current = true
        setInterviewStarted(true)
        setSessionElapsed(0)
        setChatMessages([])
        setAsrDebugEvents([])
        setCurrentQuestion('')
        setUserAnswer('')
        setCompletedInterviewId('')
        void startVideoRecording(sessionId)

        socketClient.emit('session_start', {
            session_id: sessionId,
            round_type: interviewConfig.round,
            position: interviewConfig.position,
            difficulty: interviewConfig.difficulty,
            user_id: 'default',
            training_task_id: interviewConfig.trainingTaskId || undefined,
            training_mode: interviewConfig.trainingMode || undefined,
            auto_end_min_questions: interviewConfig.auto_end_min_questions,
            auto_end_max_questions: interviewConfig.auto_end_max_questions,
            selected_question: interviewConfig.selectedQuestion
                ? {
                    id: interviewConfig.selectedQuestion.id || '',
                    question: interviewConfig.selectedQuestion.question || '',
                    category: interviewConfig.selectedQuestion.category || '',
                    round_type: interviewConfig.selectedQuestion.round_type || interviewConfig.round,
                    position: interviewConfig.selectedQuestion.position || interviewConfig.position,
                    difficulty: interviewConfig.selectedQuestion.difficulty || interviewConfig.difficulty,
                }
                : undefined,
        })
    }

    const handleStartInterview = () => {
        if (!socket) return
        startInterviewSession(socket)
    }

    useEffect(() => {
        if (!cameraReady || !socket || interviewStarted || showCompletionModal || autoStartTriggeredRef.current) {
            return
        }

        autoStartTriggeredRef.current = true
        startInterviewSession(socket)
    }, [cameraReady, socket, interviewStarted, showCompletionModal])

    const requestSessionEnd = async (socketClient: SocketClient, endedSessionId: string) => {
        clearLlmTimeout()
        clearPendingCommit()
        stopCurrentTts()
        stopAudioRecording()
        speechActiveRef.current = false
        clearSpeechPrebuffer()
        setIsEndingInterview(true)
        void stopVideoRecording(endedSessionId, true).catch((error) => {
            console.warn('[Interview] video finalize after session end failed:', error)
        })
        socketClient.emit('session_end', {
            session_id: endedSessionId,
        })
    }

    const handleEndInterview = async () => {
        if (!socket || !sessionIdRef.current || autoEndingRef.current) return
        autoEndingRef.current = true
        try {
            await requestSessionEnd(socket, sessionIdRef.current)
        } catch (error) {
            autoEndingRef.current = false
            setIsEndingInterview(false)
            console.error('[Interview] 手动结束失败:', error)
        }
    }

    const closeCompletionModal = () => {
        setShowCompletionModal(false)
    }

    const gotoCompletionTarget = (target: '/' | '/replay' | '/review' | '/report') => {
        setShowCompletionModal(false)
        if (target === '/') {
            router.push(target)
            return
        }
        const query = completedInterviewId
            ? `?interviewId=${encodeURIComponent(completedInterviewId)}`
            : ''
        router.push(`${target}${query}`)
    }

    const handleSubmitAnswer = (forcedAnswer?: string) => {
        const answerText = (forcedAnswer ?? userAnswer).trim()
        const questionText = (currentQuestion || '').trim()
        if (!socket || !sessionIdRef.current || !answerText || isProcessing || !questionText) {
            if (!questionText && answerText) {
                console.warn('[LLM] 当前还没有有效问题，跳过本次回答提交')
            }
            return
        }

        clearLlmTimeout()
        clearPendingCommit()
        setIsProcessing(true)

        appendCandidateMessage(answerText)

        socket.emit('utterance_commit', {
            session_id: sessionIdRef.current,
            turn_id: currentTurnIdRef.current,
            text: answerText,
            source: 'manual'
        })

        llmTimeoutRef.current = setTimeout(() => {
            console.warn('[LLM] 处理超时，自动解除处理中状态')
            setIsProcessing(false)
        }, 15000)

        setUserAnswer('')
    }

    const voiceInputEnabled = isVoiceSupported && (isServerAsrAvailable || isBrowserAsrSupported)
    const autoRecordStatus = !voiceInputEnabled
        ? (asrStatusMessage || (isVoiceSupported
            ? '语音识别当前不可用，请使用下方文本框继续回答。'
            : '当前浏览器无法录音，请使用下方文本框回答。'))
        : isAiSpeaking
            ? '面试官发言中，录音已自动暂停'
            : isProcessing
                ? '正在处理你的回答...'
                : answerSessionStatus === 'finalizing'
                    ? '当前回答整理中，稍候会自动续录'
                    : answerSessionStatus === 'paused_short'
                        ? '检测到停顿，继续说话会自动并入同一题回答'
                        : (isRecording || isListening)
                            ? '录音自动进行中'
                            : '等待你开始回答，系统将自动录音'

    useEffect(() => {
        if (!cameraReady || !socket || !interviewStarted || !sessionIdRef.current) return

        const emitDetectionState = () => {
            const now = Date.now()
            const pulseMetrics = rppgMetricsRef.current
            const behaviorMetrics = faceBehaviorMetricsRef.current
            const hasFace = Boolean(behaviorMetrics.hasFace || pulseMetrics.hasFace)
            if (hasFace) {
                noFaceSinceRef.current = null
            } else if (noFaceSinceRef.current === null) {
                noFaceSinceRef.current = now
            }

            const noFaceLong = !hasFace && noFaceSinceRef.current !== null && now - noFaceSinceRef.current >= 3000
            const faceCount = hasFace ? Math.max(1, Math.floor(toFiniteNumber(behaviorMetrics.faceCount, 1))) : 0

            const headPose = behaviorMetrics.headPose
            const absYaw = Math.abs(toFiniteNumber(headPose?.yaw, 0))
            const absPitch = Math.abs(toFiniteNumber(headPose?.pitch, 0))
            const absRoll = Math.abs(toFiniteNumber(headPose?.roll, 0))
            const gazeMagnitude = clamp(toFiniteNumber(behaviorMetrics.irisTracking.gaze_offset_magnitude, 0), 0, 1)
            const driftCount = Math.max(0, Math.floor(toFiniteNumber(behaviorMetrics.irisTracking.drift_count, 0)))
            const blinkRate = Math.max(0, toFiniteNumber(behaviorMetrics.blendshapes.blink_rate_per_min, 0))
            const jawOpenAvg = clamp(toFiniteNumber(behaviorMetrics.blendshapes.jaw_open_avg, 0), 0, 1)
            const faceDistanceZ = roundMetric(behaviorMetrics.landmarks3d.face_distance_z, 6, null)
            const microMovementVariance = roundMetric(behaviorMetrics.landmarks3d.micro_movement_variance, 6, null)
            const mouthOpenRatio = roundMetric(behaviorMetrics.landmarks3d.mouth_open_ratio, 4, null)
            const offScreen = hasFace ? clamp(gazeMagnitude * 130, 0, 100) : 100

            const hasLandmarks = toFiniteNumber(behaviorMetrics.landmarks3d.landmark_count, 0) >= 468
            const poseUnstable = absYaw >= 28 || absPitch >= 20 || absRoll >= 20
            const gazeDriftHigh = driftCount >= 8 || offScreen >= 35
            const blinkHigh = blinkRate >= 45
            const distanceTooClose = faceDistanceZ !== null && faceDistanceZ < -0.12
            const distanceTooFar = faceDistanceZ !== null && faceDistanceZ > -0.02

            let riskScore = 18
            if (!hasFace) {
                riskScore = noFaceLong ? 88 : 35
            } else {
                if (poseUnstable) riskScore = Math.max(riskScore, 48)
                if (gazeDriftHigh) riskScore = Math.max(riskScore, 58)
                if (blinkHigh) riskScore = Math.max(riskScore, 32)
                if (distanceTooClose || distanceTooFar) riskScore = Math.max(riskScore, 25)
                if (faceCount > 1) riskScore = Math.max(riskScore, 85)
                if (!hasLandmarks) riskScore = Math.max(riskScore, 30)

                if (pulseMetrics.status === 'unstable') {
                    riskScore = Math.max(riskScore, 24)
                } else if (pulseMetrics.status === 'error') {
                    riskScore = Math.max(riskScore, 28)
                } else if (!pulseMetrics.isReliable) {
                    riskScore = Math.max(riskScore, 20)
                } else if (pulseMetrics.hr !== null && (pulseMetrics.hr < 48 || pulseMetrics.hr > 125)) {
                    riskScore = Math.max(riskScore, 22)
                }
            }
            riskScore = clamp(riskScore, 0, 100)

            const nextRiskLevel = riskScore >= 75 ? 'HIGH' : riskScore >= 40 ? 'MEDIUM' : 'LOW'
            const nextGazeStatus = !hasFace ? 'Face Missing' : offScreen >= 35 ? 'Drifting' : 'Normal'
            const nextMouthStatus = speechActiveRef.current ? 'Speaking' : jawOpenAvg >= 0.14 ? 'Open' : 'Closed'
            const flags = [
                ...(noFaceLong ? ['no_face_long'] : []),
                ...(!hasFace ? ['face_missing'] : []),
                ...(faceCount > 1 ? ['multi_person'] : []),
                ...(poseUnstable ? ['pose_unstable'] : []),
                ...(gazeDriftHigh ? ['gaze_drift_high'] : []),
                ...(blinkHigh ? ['blink_rate_high'] : []),
                ...(distanceTooClose ? ['too_close_to_camera'] : []),
                ...(distanceTooFar ? ['too_far_from_camera'] : []),
                ...(!hasLandmarks ? ['landmark_low_confidence'] : []),
                ...(pulseMetrics.status === 'error' ? ['sensor_error'] : []),
                ...(pulseMetrics.status === 'unstable' ? ['signal_unstable'] : []),
                ...(nextRiskLevel === 'HIGH' ? ['high_risk'] : [])
            ]

            const speechExpressiveness = roundMetric(
                speechActiveRef.current ? jawOpenAvg * 100 : jawOpenAvg * 65,
                2,
                null,
            )

            const cameraInsights = {
                schema_version: 'face_insights_v1',
                landmarks_3d: {
                    landmark_count: Math.floor(toFiniteNumber(behaviorMetrics.landmarks3d.landmark_count, 0)),
                    mouth_open_ratio: mouthOpenRatio,
                    micro_movement_variance: microMovementVariance,
                    face_distance_z: faceDistanceZ,
                },
                blendshapes: {
                    available_count: Math.floor(toFiniteNumber(behaviorMetrics.blendshapes.available_count, 0)),
                    key_current: behaviorMetrics.blendshapes.key_current || {},
                    averages: behaviorMetrics.blendshapes.averages || {},
                    blink_rate_per_min: roundMetric(behaviorMetrics.blendshapes.blink_rate_per_min, 2, null),
                    brow_inner_up_avg: roundMetric(behaviorMetrics.blendshapes.brow_inner_up_avg, 4, null),
                    smile_avg: roundMetric(behaviorMetrics.blendshapes.smile_avg, 4, null),
                    jaw_open_avg: roundMetric(behaviorMetrics.blendshapes.jaw_open_avg, 4, null),
                    speech_expressiveness: speechExpressiveness,
                },
                head_pose: headPose
                    ? {
                        pitch: roundMetric(headPose.pitch, 2, 0),
                        yaw: roundMetric(headPose.yaw, 2, 0),
                        roll: roundMetric(headPose.roll, 2, 0),
                    }
                    : null,
                iris_tracking: {
                    gaze_offset_x: roundMetric(behaviorMetrics.irisTracking.gaze_offset_x, 4, null),
                    gaze_offset_y: roundMetric(behaviorMetrics.irisTracking.gaze_offset_y, 4, null),
                    gaze_offset_magnitude: roundMetric(behaviorMetrics.irisTracking.gaze_offset_magnitude, 4, null),
                    gaze_focus_score: roundMetric(behaviorMetrics.irisTracking.gaze_focus_score, 2, null),
                    drift_count: Math.floor(toFiniteNumber(behaviorMetrics.irisTracking.drift_count, 0)),
                },
                sample_count: Math.floor(toFiniteNumber(behaviorMetrics.sampleCount, 0)),
            }

            socket.emit('detection_state', {
                session_id: sessionIdRef.current,
                ts: now,
                has_face: hasFace,
                face_count: faceCount,
                off_screen_ratio: offScreen,
                rppg_reliable: pulseMetrics.isReliable,
                hr: pulseMetrics.hr,
                risk_level: nextRiskLevel,
                risk_score: riskScore,
                gaze_status: nextGazeStatus,
                mouth_status: nextMouthStatus,
                landmark_count: cameraInsights.landmarks_3d.landmark_count,
                blendshape_count: cameraInsights.blendshapes.available_count,
                gaze_drift_count: cameraInsights.iris_tracking.drift_count,
                pitch: cameraInsights.head_pose?.pitch,
                yaw: cameraInsights.head_pose?.yaw,
                roll: cameraInsights.head_pose?.roll,
                speech_expressiveness: cameraInsights.blendshapes.speech_expressiveness,
                camera_insights: cameraInsights,
                flags
            })
        }

        emitDetectionState()
        const interval = setInterval(emitDetectionState, 250)

        return () => clearInterval(interval)
    }, [
        cameraReady,
        socket,
        interviewStarted
    ])

    const liveDetection = (() => {
        const pulseMetrics = rppgMetrics
        const behaviorMetrics = faceBehaviorMetrics
        const hasFace = Boolean(behaviorMetrics.hasFace || pulseMetrics.hasFace)
        const faceCount = hasFace ? Math.max(1, Math.floor(toFiniteNumber(behaviorMetrics.faceCount, 1))) : 0
        const headPose = behaviorMetrics.headPose
        const gazeMagnitude = clamp(toFiniteNumber(behaviorMetrics.irisTracking.gaze_offset_magnitude, 0), 0, 1)
        const driftCount = Math.max(0, Math.floor(toFiniteNumber(behaviorMetrics.irisTracking.drift_count, 0)))
        const blinkRate = Math.max(0, toFiniteNumber(behaviorMetrics.blendshapes.blink_rate_per_min, 0))
        const jawOpenAvg = clamp(toFiniteNumber(behaviorMetrics.blendshapes.jaw_open_avg, 0), 0, 1)
        const faceDistanceZ = roundMetric(behaviorMetrics.landmarks3d.face_distance_z, 6, null)
        const offScreen = hasFace ? clamp(gazeMagnitude * 130, 0, 100) : 100
        const hasLandmarks = toFiniteNumber(behaviorMetrics.landmarks3d.landmark_count, 0) >= 468
        const absYaw = Math.abs(toFiniteNumber(headPose?.yaw, 0))
        const absPitch = Math.abs(toFiniteNumber(headPose?.pitch, 0))
        const absRoll = Math.abs(toFiniteNumber(headPose?.roll, 0))
        const poseUnstable = absYaw >= 28 || absPitch >= 20 || absRoll >= 20
        const gazeDriftHigh = driftCount >= 8 || offScreen >= 35
        const blinkHigh = blinkRate >= 45
        const distanceTooClose = faceDistanceZ !== null && faceDistanceZ < -0.12
        const distanceTooFar = faceDistanceZ !== null && faceDistanceZ > -0.02
        let riskScore = 18
        if (!hasFace) {
            riskScore = 35
        } else {
            if (poseUnstable) riskScore = Math.max(riskScore, 48)
            if (gazeDriftHigh) riskScore = Math.max(riskScore, 58)
            if (blinkHigh) riskScore = Math.max(riskScore, 32)
            if (distanceTooClose || distanceTooFar) riskScore = Math.max(riskScore, 25)
            if (faceCount > 1) riskScore = Math.max(riskScore, 85)
            if (!hasLandmarks) riskScore = Math.max(riskScore, 30)
            if (pulseMetrics.status === 'unstable') riskScore = Math.max(riskScore, 24)
            if (pulseMetrics.status === 'error') riskScore = Math.max(riskScore, 28)
            if (!pulseMetrics.isReliable) riskScore = Math.max(riskScore, 20)
            if (pulseMetrics.hr !== null && (pulseMetrics.hr < 48 || pulseMetrics.hr > 125)) riskScore = Math.max(riskScore, 22)
        }
        riskScore = clamp(riskScore, 0, 100)
        return {
            hasFace,
            faceCount,
            riskScore,
            riskLevel: riskScore >= 75 ? '高' : riskScore >= 40 ? '中' : '低',
            offScreen,
            gazeMagnitude,
            driftCount,
            blinkRate,
            jawOpenAvg,
            headPose,
            faceDistanceZ,
        }
    })()

    const difficultyText = interviewConfig.difficulty === 'easy'
        ? '简单'
        : interviewConfig.difficulty === 'medium'
            ? '中等'
            : '困难'
    const displayQuestion = currentQuestion || '面试官正在准备下一道问题，请稍候。'
    const formatTime = (seconds: number) => {
        const minutes = Math.floor(seconds / 60).toString().padStart(2, '0')
        const restSeconds = (seconds % 60).toString().padStart(2, '0')
        return `${minutes}:${restSeconds}`
    }
    const formatDebugTime = (timestamp: number) => {
        const msTs = timestamp > 1e12 ? timestamp : timestamp * 1000
        const date = new Date(msTs)
        return date.toLocaleTimeString()
    }
    const buildDebugPreview = (item: AsrDebugEvent) => {
        return (
            item.final_preview
            || item.partial_preview
            || item.segment_preview
            || item.answer_preview
            || item.text_snapshot
            || item.details
            || item.reason_detail
            || ''
        )
    }
    if (interviewStarted) {
        return (
            <div
                className="interview-shell-bg relative flex min-h-[100dvh] w-full flex-col overflow-hidden font-sans text-[#111111] md:h-[100dvh]"
            >
                <header className="z-10 shrink-0 border-b border-[#E5E5E5] bg-white/88 px-3 py-2 backdrop-blur-md sm:px-4 md:px-5">
                    <div className="flex items-center justify-between gap-4">
                        <div className="flex min-w-0 items-center gap-3">
                            <button
                                onClick={handleEndInterview}
                                disabled={isEndingInterview}
                                type="button"
                                className={`rounded-full p-2 text-[#666666] transition-colors ${isEndingInterview
                                    ? 'cursor-wait opacity-60'
                                    : 'hover:bg-[#F5F5F5] hover:text-[#111111]'
                                    }`}
                                aria-label="结束并返回"
                            >
                                <X size={18} />
                            </button>
                            <div className="h-4 w-px bg-[#E5E5E5]" />
                            <span className="truncate text-sm font-semibold tracking-tight text-[#111111]">AI 面试进行中</span>
                        </div>
                        <div className="flex items-center gap-3 sm:gap-6">
                            <button
                                onClick={handleEndInterview}
                                disabled={isEndingInterview}
                                className={`inline-flex items-center rounded-full border border-[#E5E5E5] bg-white px-4 py-1.5 text-sm font-medium text-[#111111] transition-colors ${isEndingInterview ? 'cursor-wait opacity-60' : 'hover:bg-[#F5F5F5]'
                                    }`}
                                type="button"
                            >
                                结束面试
                            </button>
                            <div className="flex items-center gap-2 text-sm text-[#666666]">
                                <span className={`h-2 w-2 rounded-full ${isRecording ? 'bg-[#E27A5F] animate-pulse' : isAiSpeaking ? 'bg-[#f59e0b] animate-pulse' : 'bg-[#2E6A45]'}`} />
                                {isRecording ? 'Recording' : isAiSpeaking ? 'Interviewer Speaking' : 'Session Active'}
                            </div>
                            <span className="w-12 text-right font-mono text-sm text-[#111111]">{formatTime(sessionElapsed)}</span>
                        </div>
                    </div>
                </header>

                <main className="flex min-h-0 w-full flex-1 flex-col gap-2.5 overflow-hidden p-2 md:flex-row md:gap-2.5 md:p-2.5 lg:gap-3 lg:p-3">
                    <div className="flex min-w-0 flex-1 flex-col gap-2.5 md:flex-[1.58]">
                        <div className="relative min-h-[40svh] overflow-hidden rounded-2xl border border-[#1D1D1D] bg-[#0B0B0D] shadow-[0_22px_40px_-28px_rgba(0,0,0,0.75)] md:min-h-0 md:flex-[1_1_64%]">
                            <video
                                ref={videoRef}
                                autoPlay
                                playsInline
                                muted
                                className="h-full w-full -scale-x-100 object-cover"
                            />
                            <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-black/55 to-transparent" />
                            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/60 to-transparent" />
                            {isRecording && (
                                <div className="absolute right-4 top-4 z-20 inline-flex items-center gap-2 rounded-full border border-white/15 bg-black/45 px-3 py-1.5 text-[11px] font-medium uppercase tracking-wider text-white backdrop-blur">
                                    <span className="h-2 w-2 rounded-full bg-[#E27A5F] animate-pulse" />
                                    REC
                                </div>
                            )}
                            {!cameraReady && (
                                <div className="absolute inset-0 flex items-center justify-center bg-black/70 text-white">
                                    <div className="flex items-center gap-2 text-sm">
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        加载摄像头中...
                                    </div>
                                </div>
                            )}
                            <div className="absolute left-3 top-3 z-20 max-w-[calc(100%-1.5rem)] rounded-xl border border-white/15 bg-black/40 px-3 py-1.5 text-xs text-white backdrop-blur sm:max-w-[84%]">
                                <p className="mb-1 text-[10px] uppercase tracking-wider text-white/70">当前问题</p>
                                <p className="line-clamp-3 text-sm leading-relaxed">{displayQuestion}</p>
                            </div>
                            <div className="absolute bottom-3 left-3 inline-flex items-center gap-2 rounded-xl border border-white/10 bg-black/45 px-3 py-1.5 text-xs text-white backdrop-blur">
                                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/20">
                                    <User size={14} />
                                </span>
                                You
                            </div>
                            <div className="absolute bottom-3 right-3 flex h-16 w-28 items-center justify-center overflow-hidden rounded-xl border border-white/10 bg-[#1F1F22] shadow-2xl sm:h-20 sm:w-36">
                                <span className={`h-3 w-3 rounded-full ${isAiSpeaking ? 'animate-pulse bg-[#E27A5F]' : 'bg-white/75'}`} />
                                <span className={`absolute h-10 w-10 rounded-full border border-white/20 ${isAiSpeaking ? 'animate-ping' : ''}`} />
                                <span className="absolute bottom-2 left-2 text-[10px] uppercase tracking-wider text-white/70">
                                    Interviewer · {isAiSpeaking ? 'Speaking' : 'Waiting'}
                                </span>
                            </div>
                        </div>

                        <div className="min-h-[160px] shrink-0 rounded-2xl border border-[#E5E5E5] bg-white p-3.5 shadow-sm md:h-[clamp(132px,20vh,180px)] lg:p-4">
                            <div className="mb-3 flex h-full flex-col">
                                <div className="flex-1 overflow-y-auto pr-2">
                                    {userAnswer ? (
                                        <p className="text-base leading-relaxed text-[#111111]">
                                            {userAnswer}
                                            {isRecording && <span className="ml-1 inline-block h-5 w-2 animate-pulse bg-[#111111] align-middle" />}
                                        </p>
                                    ) : (
                                        <p className="text-base italic leading-relaxed text-[#999999]">
                                            {isProcessing ? '正在处理你的回答...' : '你的语音转录会实时显示在这里...'}
                                        </p>
                                    )}
                                </div>

                                <div className="flex shrink-0 items-center justify-between border-t border-[#F5F5F5] pt-2">
                                    <div className="flex items-center gap-4">
                                        <div
                                            aria-label="自动录音状态"
                                            className={`relative inline-flex h-11 w-11 items-center justify-center rounded-full ${isRecording
                                                ? 'bg-[#111111] text-white'
                                                : voiceInputEnabled
                                                    ? (isAiSpeaking ? 'bg-[#ECEAE4] text-[#7D776B]' : 'bg-[#F1EFEA] text-[#555046]')
                                                    : 'bg-[#E7E3DB] text-[#9A9387]'
                                                }`}
                                        >
                                            {isRecording && (
                                                <span className="absolute inset-0 rounded-full border border-[#111111]/65 animate-ping" />
                                            )}
                                            <Mic size={18} />
                                        </div>

                                        {isRecording && (
                                            <div className="flex h-8 items-center gap-1 overflow-hidden">
                                                <span className="h-2 w-1 animate-pulse rounded-full bg-[#111111]" />
                                                <span className="h-4 w-1 animate-pulse rounded-full bg-[#111111] [animation-delay:120ms]" />
                                                <span className="h-3 w-1 animate-pulse rounded-full bg-[#111111] [animation-delay:240ms]" />
                                                <span className="h-5 w-1 animate-pulse rounded-full bg-[#111111] [animation-delay:360ms]" />
                                                <span className="h-2 w-1 animate-pulse rounded-full bg-[#111111] [animation-delay:480ms]" />
                                            </div>
                                        )}
                                        <p className="line-clamp-2 text-xs leading-5 text-[#777268]">{autoRecordStatus}</p>
                                    </div>

                                    <button
                                        onClick={() => handleSubmitAnswer()}
                                        disabled={!userAnswer.trim() || !currentQuestion || isProcessing || isAiSpeaking}
                                        className="inline-flex items-center gap-1 rounded-full bg-[#111111] px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#222222] disabled:cursor-not-allowed disabled:bg-[#c8c2b7]"
                                    >
                                        提交答案
                                        <ArrowRight size={14} />
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <aside className="flex min-h-[320px] w-full shrink-0 flex-col overflow-hidden rounded-2xl border border-[#E5E5E5] bg-white/95 shadow-sm md:min-h-0 md:w-[min(280px,28vw)] lg:w-[300px]">
                        <div className="border-b border-[#E5E5E5] bg-white px-4 py-3">
                            <div className="flex items-center justify-between gap-2">
                                <div>
                                    <h3 className="text-sm font-medium text-[#111111]">实时检测指标</h3>
                                    <p className="mt-1 text-xs text-[#666666]">
                                        视觉 {formatDetectionStatus(faceBehaviorMetrics.status)} · 生理 {formatDetectionStatus(rppgMetrics.status)}
                                    </p>
                                </div>
                                <span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold ${liveDetection.riskScore >= 75
                                    ? 'bg-[#FDECEC] text-[#9D3A2E]'
                                    : liveDetection.riskScore >= 40
                                        ? 'bg-[#FFF4D8] text-[#8A5A00]'
                                        : 'bg-[#EAF6EF] text-[#256A43]'
                                    }`}>
                                    风险{liveDetection.riskLevel}
                                </span>
                            </div>

                            <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                                <div className="rounded-lg border border-[#EFEDE8] bg-[#FAFAFA] p-2">
                                    <div className="flex items-center gap-1.5 text-[#777268]"><Eye size={13} />人脸</div>
                                    <p className="mt-1 font-mono text-sm text-[#111111]">{liveDetection.hasFace ? `${liveDetection.faceCount} 张` : '未检测'}</p>
                                    <p className="mt-0.5 text-[10px] text-[#8A8376]">关键点 {formatDetectionMetric(faceBehaviorMetrics.landmarks3d.landmark_count, 0)}</p>
                                </div>
                                <div className="rounded-lg border border-[#EFEDE8] bg-[#FAFAFA] p-2">
                                    <div className="flex items-center gap-1.5 text-[#777268]"><HeartPulse size={13} />心率</div>
                                    <p className="mt-1 font-mono text-sm text-[#111111]">{rppgMetrics.hr !== null ? formatDetectionMetric(rppgMetrics.hr, 1, ' bpm') : '--'}</p>
                                    <p className="mt-0.5 text-[10px] text-[#8A8376]">SQI {formatDetectionMetric(rppgMetrics.sqi, 2)} · {rppgMetrics.isReliable ? '可靠' : '待稳定'}</p>
                                </div>
                                <div className="rounded-lg border border-[#EFEDE8] bg-[#FAFAFA] p-2">
                                    <div className="flex items-center gap-1.5 text-[#777268]"><Activity size={13} />视线</div>
                                    <p className="mt-1 font-mono text-sm text-[#111111]">{formatDetectionMetric(100 - liveDetection.offScreen, 1, '%')}</p>
                                    <p className="mt-0.5 text-[10px] text-[#8A8376]">偏移 {formatDetectionMetric(liveDetection.gazeMagnitude, 4)} · 漂移 {liveDetection.driftCount}</p>
                                </div>
                                <div className="rounded-lg border border-[#EFEDE8] bg-[#FAFAFA] p-2">
                                    <div className="flex items-center gap-1.5 text-[#777268]"><Gauge size={13} />风险</div>
                                    <p className="mt-1 font-mono text-sm text-[#111111]">{formatDetectionMetric(liveDetection.riskScore, 0, '/100')}</p>
                                    <p className="mt-0.5 text-[10px] text-[#8A8376]">样本 {formatDetectionMetric(faceBehaviorMetrics.sampleCount, 0)} · FPS {formatDetectionMetric(rppgMetrics.fps, 1)}</p>
                                </div>
                            </div>

                            <div className="mt-2 rounded-lg border border-[#EFEDE8] bg-[#FCFCFB] p-2 text-[11px] text-[#666666]">
                                <div className="grid grid-cols-3 gap-1 font-mono text-[#111111]">
                                    <span>Pitch {formatDetectionMetric(liveDetection.headPose?.pitch, 1, '°')}</span>
                                    <span>Yaw {formatDetectionMetric(liveDetection.headPose?.yaw, 1, '°')}</span>
                                    <span>Roll {formatDetectionMetric(liveDetection.headPose?.roll, 1, '°')}</span>
                                </div>
                                <div className="mt-1 grid grid-cols-3 gap-1 font-mono text-[#111111]">
                                    <span>眨眼 {formatDetectionMetric(liveDetection.blinkRate, 1)}</span>
                                    <span>开口 {formatDetectionMetric(faceBehaviorMetrics.landmarks3d.mouth_open_ratio, 3)}</span>
                                    <span>jaw {formatDetectionMetric(liveDetection.jawOpenAvg, 3)}</span>
                                </div>
                                <div className="mt-1 grid grid-cols-3 gap-1 font-mono text-[#111111]">
                                    <span>smile {formatDetectionMetric(faceBehaviorMetrics.blendshapes.smile_avg, 3)}</span>
                                    <span>brow {formatDetectionMetric(faceBehaviorMetrics.blendshapes.brow_inner_up_avg, 3)}</span>
                                    <span>Z {formatDetectionMetric(liveDetection.faceDistanceZ, 4)}</span>
                                </div>
                            </div>
                        </div>

                        <div className="border-b border-[#E5E5E5] bg-[#FAFAFA] px-4 py-3">
                            <h3 className="text-sm font-medium text-[#111111]">面试转写</h3>
                            <p className="mt-1 text-xs text-[#666666]">已记录 {chatMessages.length} 条对话</p>
                        </div>

                        <div
                            ref={chatScrollContainerRef}
                            className="min-h-0 max-h-[calc(100vh-280px)] space-y-4 overflow-y-auto bg-[#FCFCFB] p-4"
                        >
                            {chatMessages.length === 0 ? (
                                <div className="rounded-lg border border-dashed border-[#D9D4CA] bg-[#FAFAFA] p-6 text-center text-sm text-[#777268]">
                                    <div className="mx-auto mb-2 inline-flex h-9 w-9 items-center justify-center rounded-full bg-white text-[#777268]">
                                        <MessageSquare size={16} />
                                    </div>
                                    <p>等待面试官提问...</p>
                                    <p className="mt-1 text-xs text-[#9B9488]">系统会在收到首问后自动开始记录</p>
                                </div>
                            ) : (
                                chatMessages.map((msg, idx) => (
                                    <div
                                        key={idx}
                                        className={`flex flex-col ${msg.role === 'candidate' ? 'items-end' : 'items-start'}`}
                                    >
                                        <div className="mb-1.5 flex items-center gap-2 px-1">
                                            <span className="text-[11px] font-medium uppercase tracking-wider text-[#111111]">
                                                {msg.role === 'interviewer' ? 'Interviewer' : 'You'}
                                            </span>
                                            <span className="text-[10px] text-[#999999]">{msg.timestamp}</span>
                                        </div>
                                        <div
                                            className={`max-w-[92%] rounded-2xl p-2.5 text-sm leading-relaxed ${msg.role === 'candidate'
                                                ? 'rounded-tr-sm bg-[#111111] text-white shadow-[0_12px_20px_-18px_rgba(0,0,0,0.9)]'
                                                : 'rounded-tl-sm border border-[#E7E3DB] bg-[#F7F6F2] text-[#111111]'
                                                }`}
                                        >
                                            {msg.content}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>

                        {ASR_DEBUG_PANEL_ENABLED && (
                            <div className="border-t border-[#E5E5E5] bg-[#FAFAFA]">
                                <div className="flex items-center justify-between gap-2 px-3 py-2">
                                    <div>
                                        <p className="text-[11px] font-semibold uppercase tracking-wider text-[#111111]">语音识别诊断</p>
                                        <p className="text-[10px] text-[#777268]">{asrDebugEvents.length} 条事件</p>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        <button
                                            onClick={() => setShowAsrDebugPanel((prev) => !prev)}
                                            className="rounded border border-[#DAD6CE] bg-white px-2 py-1 text-[10px] text-[#333333] hover:bg-[#F5F5F5]"
                                        >
                                            {showAsrDebugPanel ? '收起' : '展开'}
                                        </button>
                                        <button
                                            onClick={() => setAsrDebugEvents([])}
                                            className="rounded border border-[#DAD6CE] bg-white px-2 py-1 text-[10px] text-[#333333] hover:bg-[#F5F5F5]"
                                        >
                                            清空
                                        </button>
                                    </div>
                                </div>
                                {showAsrDebugPanel && (
                                    <div
                                        ref={asrDebugScrollContainerRef}
                                        className="max-h-44 space-y-1.5 overflow-y-auto border-t border-[#E5E5E5] px-3 py-2"
                                    >
                                        {asrDebugEvents.length === 0 ? (
                                            <p className="text-[11px] text-[#8A8376]">等待后端 ASR 调试事件...</p>
                                        ) : (
                                            asrDebugEvents.map((item, index) => {
                                                const preview = buildDebugPreview(item)
                                                return (
                                                    <div
                                                        key={`${item.timestamp}_${item.event}_${index}`}
                                                        className="rounded-md border border-[#E8E4DC] bg-white px-2 py-1.5"
                                                    >
                                                        <div className="flex items-center justify-between gap-2">
                                                            <p className="truncate text-[10px] font-semibold text-[#111111]">{item.event}</p>
                                                            <span className="shrink-0 text-[10px] text-[#888274]">{formatDebugTime(item.timestamp)}</span>
                                                        </div>
                                                        <p className="mt-0.5 text-[10px] text-[#666666]">
                                                            gen:{String(item.asr_generation || '-')} | epoch:{String(item.speech_epoch || '-')}
                                                        </p>
                                                        {preview && (
                                                            <p className="mt-0.5 line-clamp-2 text-[10px] leading-4 text-[#333333]">{preview}</p>
                                                        )}
                                                    </div>
                                                )
                                            })
                                        )}
                                    </div>
                                )}
                            </div>
                        )}
                    </aside>
                </main>

                {isEndingInterview && (
                    <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/30 p-4 backdrop-blur-sm">
                        <div className="w-full max-w-sm rounded-3xl border border-white/20 bg-white/92 p-6 text-center shadow-2xl">
                            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[#111111] text-white">
                                <Loader2 className="h-6 w-6 animate-spin" />
                            </div>
                            <h3 className="mt-4 text-xl font-semibold text-[#111111]">正在结束面试</h3>
                            <p className="mt-2 text-sm leading-6 text-[#666666]">
                                正在保存会话内容并生成报告，你可以稍等几秒。
                            </p>
                        </div>
                    </div>
                )}
            </div>
        )
    }

    return (
        <div className="-m-3 h-[100dvh] overflow-hidden bg-[#F3F2EF] p-3 sm:-m-4 sm:p-4 lg:-m-5">
            <div className="mx-auto flex h-full max-w-3xl items-center justify-center">
                <section className="w-full rounded-2xl border border-[#E5E5E5] bg-white p-5 shadow-sm sm:p-6">
                    <div className="mb-4 flex items-center gap-3 text-[#111111]">
                        <Loader2 className="h-5 w-5 animate-spin" />
                        <h2 className="text-lg font-semibold">正在进入面试场景</h2>
                    </div>
                    <p className="text-sm leading-6 text-[#666666]">
                        系统正在连接面试会话与实时识别通道，请稍候。
                    </p>
                    <div className="mt-4 grid gap-2 rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-3 text-xs text-[#666666] sm:grid-cols-3">
                        <div>面试轮次：<span className="font-medium text-[#111111]">{interviewConfig.roundName}</span></div>
                        <div>目标岗位：<span className="font-medium text-[#111111]">{interviewConfig.position.replace('_', ' ')}</span></div>
                        <div>难度：<span className="font-medium text-[#111111]">{difficultyText}</span></div>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2.5">
                        <button
                            onClick={() => router.push('/interview/setup')}
                            className="inline-flex items-center rounded-lg border border-[#E5E5E5] bg-white px-4 py-2 text-sm font-medium text-[#111111] hover:bg-[#F5F5F5]"
                        >
                            返回开始前检查
                        </button>
                        <button
                            onClick={handleStartInterview}
                            disabled={!cameraReady || !socket}
                            className="inline-flex items-center gap-2 rounded-lg bg-[#111111] px-4 py-2 text-sm font-medium text-white hover:bg-[#222222] disabled:cursor-not-allowed disabled:bg-[#cbc5b9]"
                        >
                            立即重试连接
                            <ArrowRight className="h-4 w-4" />
                        </button>
                    </div>
                </section>
            </div>

            {showCompletionModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4 backdrop-blur-sm">
                    <div className="w-full max-w-md overflow-hidden rounded-3xl border border-[#E5E5E5] bg-[#FAF9F6] shadow-2xl animate-scale-up">
                        <div className="h-1 bg-[#111111]" />
                        <div className="p-8">
                            <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-[#111111] text-white">
                                <CheckCircle2 className="h-8 w-8" />
                            </div>

                            <h3 className="text-center text-2xl font-semibold tracking-tight text-[#111111]">会话已完成</h3>
                            <p className="mt-2 text-center text-sm leading-6 text-[#666666]">系统已生成本场即时报告；深度复盘（单题与视频）已拆分到独立复盘页。</p>

                            <div className="mt-6 rounded-2xl border border-[#E5E5E5] bg-white p-4 text-sm text-[#555555]">
                                <p className="font-medium text-[#111111]">已完成事项</p>
                                <p className="mt-1">语音转写、问题追问链路与生理信号评估均已归档。</p>
                                {completedInterviewId && (
                                    <p className="mt-2 text-xs text-[#777268]">会话 ID：{completedInterviewId}</p>
                                )}
                            </div>

                            <div className="mt-6 grid gap-2 sm:grid-cols-3">
                                <button
                                    onClick={() => gotoCompletionTarget('/review')}
                                    className="inline-flex items-center justify-center rounded-xl bg-[#111111] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-[#222222]"
                                >
                                    进入复盘清单
                                </button>
                                <button
                                    onClick={() => gotoCompletionTarget('/report')}
                                    className="inline-flex items-center justify-center rounded-xl border border-[#E5E5E5] px-4 py-2.5 text-sm font-medium text-[#111111] transition hover:bg-[#F5F5F5]"
                                >
                                    查看即时报告
                                </button>
                                <button
                                    onClick={() => gotoCompletionTarget('/')}
                                    className="inline-flex items-center justify-center rounded-xl border border-[#E5E5E5] px-4 py-2.5 text-sm font-medium text-[#111111] transition hover:bg-[#F5F5F5]"
                                >
                                    返回工作台
                                </button>
                            </div>

                            <div className="mt-2">
                                <button
                                    onClick={() => gotoCompletionTarget('/replay')}
                                    className="w-full inline-flex items-center justify-center rounded-xl border border-[#E5E5E5] px-4 py-2.5 text-sm font-medium text-[#111111] transition hover:bg-[#F5F5F5]"
                                >
                                    进入视频复盘
                                </button>
                            </div>

                            <button
                                onClick={closeCompletionModal}
                                className="mt-3 w-full text-center text-xs text-[#666666] hover:text-[#111111]"
                            >
                                暂不跳转
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}



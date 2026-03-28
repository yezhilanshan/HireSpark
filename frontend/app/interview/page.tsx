'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import SocketClient from '@/lib/socket'
import { useFacePhysRppg } from '@/lib/facephys/useFacePhysRppg'
import { Home, FileText, Mic, Radar } from 'lucide-react'

interface ChatMessage {
    role: 'interviewer' | 'candidate'
    content: string
    timestamp: string
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
    const [socket, setSocket] = useState<SocketClient | null>(null)

    const [cameraReady, setCameraReady] = useState(false)
    const [interviewStarted, setInterviewStarted] = useState(false)

    // 面试配置
    const [interviewConfig, setInterviewConfig] = useState({
        round: 'technical',
        roundName: '技术基础面',
        position: 'java_backend',
        difficulty: 'medium'
    })

    // 聊天相关
    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
    const [currentQuestion, setCurrentQuestion] = useState('')
    const [userAnswer, setUserAnswer] = useState('')
    const [answerSessionStatus, setAnswerSessionStatus] = useState('idle')
    const [isProcessing, setIsProcessing] = useState(false)
    const [isVoiceSupported, setIsVoiceSupported] = useState(true)
    const [isBrowserAsrSupported, setIsBrowserAsrSupported] = useState(false)
    const [isServerAsrAvailable, setIsServerAsrAvailable] = useState(true)
    const [asrStatusMessage, setAsrStatusMessage] = useState('')
    const [isListening, setIsListening] = useState(false)
    const [isAiSpeaking, setIsAiSpeaking] = useState(false)
    const [isRecording, setIsRecording] = useState(false)

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
    const pendingTtsTextRef = useRef('')
    const answerSessionIdRef = useRef('')
    const committedAnswerSessionIdsRef = useRef<Set<string>>(new Set())
    const userAnswerRef = useRef('')
    const speechActiveRef = useRef(false)
    const consecutiveSpeechFramesRef = useRef(0)
    const lastSpeechAtRef = useRef(0)
    const speechPrebufferRef = useRef<ArrayBuffer[]>([])
    const noFaceSinceRef = useRef<number | null>(null)
    const llmTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const pendingCommitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const audioContextRef = useRef<AudioContext | null>(null)
    const audioWorkletNodeRef = useRef<AudioWorkletNode | null>(null)
    const browserAsrRecognitionRef = useRef<SpeechRecognitionLike | null>(null)
    const browserAsrFallbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const browserAsrActiveRef = useRef(false)
    const browserAsrStopRequestedRef = useRef(false)
    const browserAsrFinalTextRef = useRef('')
    const browserAsrInterimTextRef = useRef('')
    const lastServerTranscriptAtRef = useRef(0)
    const answerSessionStatusRef = useRef('idle')
    const asrLockedRef = useRef(false)
    const socketRef = useRef<SocketClient | null>(null)
    const chatScrollContainerRef = useRef<HTMLDivElement | null>(null)
    // TTS 音频播放
    const currentTtsAudioRef = useRef<HTMLAudioElement | null>(null)
    const currentTtsUrlRef = useRef<string | null>(null)
    const browserTtsUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null)
    const browserTtsActiveRef = useRef(false)
    const ttsAudioQueueRef = useRef<Array<{ audio: string; jobId: string; turnId: string; mimeType: string }>>([])
    const isTTSSpeakingRef = useRef(false)
    const ttsSafetyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const rppgMetrics = useFacePhysRppg(videoRef, cameraReady && interviewStarted)

    const clearLlmTimeout = () => {
        if (llmTimeoutRef.current) {
            clearTimeout(llmTimeoutRef.current)
            llmTimeoutRef.current = null
        }
    }

    const clearTtsTimers = () => {
        if (ttsSafetyTimerRef.current) {
            clearTimeout(ttsSafetyTimerRef.current)
            ttsSafetyTimerRef.current = null
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

    const enqueueSpeechPrebuffer = (buffer: ArrayBuffer, maxChunks = 6) => {
        speechPrebufferRef.current.push(buffer)
        if (speechPrebufferRef.current.length > maxChunks) {
            speechPrebufferRef.current.splice(0, speechPrebufferRef.current.length - maxChunks)
        }
    }

    const setServerAsrAvailability = (available: boolean, message = '') => {
        isServerAsrAvailableRef.current = available
        setIsServerAsrAvailable(available)
        setAsrStatusMessage(message)
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
        setAnswerSessionStatus('idle')
    }

    const stopCurrentTts = () => {
        clearTtsTimers()
        ttsAudioQueueRef.current = []
        pendingTtsTextRef.current = ''
        isTTSSpeakingRef.current = false
        isAiSpeakingRef.current = false
        setIsAiSpeaking(false)

        if (currentTtsAudioRef.current) {
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

        clearTtsTimers()
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
        }
        utterance.onerror = (error) => {
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
                        nextFinal = `${nextFinal} ${transcript}`.trim()
                    } else {
                        nextInterim = `${nextInterim} ${transcript}`.trim()
                    }
                }

                browserAsrFinalTextRef.current = nextFinal
                browserAsrInterimTextRef.current = nextInterim
                const mergedText = [nextFinal, nextInterim].filter(Boolean).join(' ').trim()
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

    const scheduleBrowserAsrFallback = () => {
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

        const delay = isServerAsrAvailableRef.current ? 1600 : 120
        browserAsrFallbackTimerRef.current = setTimeout(() => {
            const noServerTranscript = Date.now() - lastServerTranscriptAtRef.current > 1200
            if (!isServerAsrAvailableRef.current || noServerTranscript) {
                startBrowserSpeechRecognition()
            }
        }, delay)
    }

    useEffect(() => {
        interviewStartedRef.current = interviewStarted
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
            setInterviewConfig({
                round: config.round || 'technical',
                roundName: roundMap[config.round] || '技术基础面',
                position: config.position || 'java_backend',
                difficulty: config.difficulty || 'medium'
            })
        }

        initCamera()
        initSocket()
        initAudioRecording()

        return () => {
            clearLlmTimeout()
            clearTtsTimers()
            clearPendingCommit()
            stopCurrentTts()
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
                video: { width: 640, height: 480 }
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
        } catch (error) {
            console.error('Camera error:', error)
            alert('Camera access denied')
            router.push('/')
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
        setIsAiSpeaking(true)
        isAiSpeakingRef.current = true
        isTTSSpeakingRef.current = true
        clearTtsTimers()

        ttsSafetyTimerRef.current = setTimeout(() => {
            if (isTTSSpeakingRef.current && !currentTtsAudioRef.current && ttsAudioQueueRef.current.length === 0) {
                console.warn('[TTS] 超时未收到音频，切换到浏览器播报')
                playBrowserTts(pendingTtsTextRef.current)
            }
        }, 4000)
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
                console.log('[TTS] 播放完成')
                if (currentTtsUrlRef.current) {
                    URL.revokeObjectURL(currentTtsUrlRef.current)
                    currentTtsUrlRef.current = null
                }
                currentTtsAudioRef.current = null
                if (ttsAudioQueueRef.current.length === 0) {
                    clearTtsTimers()
                    pendingTtsTextRef.current = ''
                    isTTSSpeakingRef.current = false
                    isAiSpeakingRef.current = false
                    setIsAiSpeaking(false)
                }
                playNextTtsChunk()
            }
            audio.onerror = (error) => {
                console.error('[TTS] 播放错误:', error)
                stopCurrentTts()
            }

            if (browserTtsActiveRef.current && typeof window !== 'undefined' && 'speechSynthesis' in window) {
                window.speechSynthesis.cancel()
                browserTtsActiveRef.current = false
            }

            audio.play().catch((err) => {
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
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            })

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
                    const speechThreshold = speechActiveRef.current ? 0.010 : 0.020
                    const isSpeechChunk = rms >= speechThreshold
                    enqueueSpeechPrebuffer(pcmData)

                    if (isSpeechChunk) {
                        consecutiveSpeechFramesRef.current += 1
                        lastSpeechAtRef.current = now
                        if (!speechActiveRef.current && consecutiveSpeechFramesRef.current >= 3) {
                            speechActiveRef.current = true
                            clearPendingCommit()
                            browserAsrFinalTextRef.current = ''
                            browserAsrInterimTextRef.current = ''
                            lastServerTranscriptAtRef.current = 0
                            const prebufferChunks = [...speechPrebufferRef.current]
                            if (isServerAsrAvailableRef.current) {
                                socketRef.current.emit('speech_start', {
                                    session_id: sessionIdRef.current,
                                    turn_id: currentTurnIdRef.current
                                })
                                for (const chunk of prebufferChunks) {
                                    socketRef.current.emit('audio_chunk', {
                                        session_id: sessionIdRef.current,
                                        turn_id: currentTurnIdRef.current,
                                        audio: arrayBufferToBase64(chunk)
                                    })
                                }
                            }
                            scheduleBrowserAsrFallback()
                            clearSpeechPrebuffer()
                            return
                        }
                    } else {
                        consecutiveSpeechFramesRef.current = 0
                    }

                    if (speechActiveRef.current && now - lastSpeechAtRef.current >= 900) {
                        speechActiveRef.current = false
                        if (isServerAsrAvailableRef.current) {
                            socketRef.current.emit('speech_end', {
                                session_id: sessionIdRef.current,
                                turn_id: currentTurnIdRef.current
                            })
                        }
                        stopBrowserSpeechRecognition()
                        clearSpeechPrebuffer()
                    }

                    // 只在检测到用户说话时上传音频，避免长时间静音导致服务端 ASR 会话超时。
                    const shouldSendAudio = speechActiveRef.current && isServerAsrAvailableRef.current
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
        setIsRecording(true)
        setIsListening(true)
        console.log('[ASR] 开始录音')
    }

    const stopAudioRecording = () => {
        if (!isRecordingRef.current && !speechActiveRef.current && !pendingCommitTimerRef.current) {
            return
        }
        clearPendingCommit()
        clearBrowserAsrFallbackTimer()
        stopBrowserSpeechRecognition()
        speechActiveRef.current = false
        consecutiveSpeechFramesRef.current = 0
        clearSpeechPrebuffer()
        isRecordingRef.current = false
        setIsRecording(false)
        setIsListening(false)
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
            socketClient.off('asr_partial')
            socketClient.off('asr_final')
            socketClient.off('tts_chunk')
            socketClient.off('tts_stop')
            socketClient.off('session_control_notice')
            socketClient.off('pipeline_error')
            socketClient.off('error')
            socketClient.off('interview_ended')

            socketClient.on('orchestrator_state', (data: any) => {
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
                if (sessionIdRef.current && data.session_id !== sessionIdRef.current) return
                if (typeof data?.interrupt_epoch === 'number' && data.interrupt_epoch < interruptEpochRef.current) return

                if (data.session_id) {
                    sessionIdRef.current = data.session_id
                }
                if (data.turn_id) {
                    currentTurnIdRef.current = data.turn_id
                }
                asrLockedRef.current = false
                resetAnswerSessionUi()

                setCurrentQuestion(data.display_text)
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

                if (data?.display_text || data?.final_text || data?.live_text || data?.merged_text_draft) {
                    lastServerTranscriptAtRef.current = Date.now()
                    if (browserAsrActiveRef.current) {
                        stopBrowserSpeechRecognition()
                    }
                }

                setAnswerSessionStatus(data?.status || 'idle')

                const displayText = data?.display_text || data?.final_text || data?.live_text || data?.merged_text_draft || ''
                if (typeof displayText === 'string') {
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

            socketClient.on('asr_partial', (data: any) => {
                if (!data?.session_id || data.session_id !== sessionIdRef.current) return
                if (data?.turn_id && currentTurnIdRef.current && data.turn_id !== currentTurnIdRef.current) return
                if (typeof data?.interrupt_epoch === 'number' && data.interrupt_epoch < interruptEpochRef.current) return
                lastServerTranscriptAtRef.current = Date.now()
                if (browserAsrActiveRef.current) {
                    stopBrowserSpeechRecognition()
                }
                if (!answerSessionIdRef.current && data?.text) {
                    setUserAnswer(data.text)
                }
            })

            socketClient.on('asr_final', (data: any) => {
                if (!data?.session_id || data.session_id !== sessionIdRef.current) return
                if (data?.turn_id && currentTurnIdRef.current && data.turn_id !== currentTurnIdRef.current) return
                if (typeof data?.interrupt_epoch === 'number' && data.interrupt_epoch < interruptEpochRef.current) return
                lastServerTranscriptAtRef.current = Date.now()
                if (browserAsrActiveRef.current) {
                    stopBrowserSpeechRecognition()
                }
                if (!answerSessionIdRef.current && (data?.full_text || data?.text)) {
                    setUserAnswer(data.full_text || data.text)
                }
            })

            socketClient.on('tts_chunk', (data: any) => {
                if (!data?.audio || !data?.session_id) return
                if (data.session_id !== sessionIdRef.current) return
                if (typeof data?.interrupt_epoch === 'number' && data.interrupt_epoch < interruptEpochRef.current) return
                if (activeTtsJobIdRef.current && data?.job_id && data.job_id !== activeTtsJobIdRef.current) return
                if (browserTtsActiveRef.current) {
                    return
                }

                if (ttsSafetyTimerRef.current) {
                    clearTimeout(ttsSafetyTimerRef.current)
                    ttsSafetyTimerRef.current = null
                }
                ttsAudioQueueRef.current.push({
                    audio: data.audio,
                    jobId: data.job_id || '',
                    turnId: data.turn_id || '',
                    mimeType: data.mime_type || 'audio/mpeg'
                })
                playNextTtsChunk()
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

                speakText(data.spoken_text || data.display_text)
                setChatMessages(prev => [...prev, {
                    role: 'interviewer',
                    content: data.display_text,
                    timestamp: new Date().toLocaleTimeString()
                }])
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
                if (data?.code === 'TTS_SYNTH_FAIL' && pendingTtsTextRef.current) {
                    playBrowserTts(pendingTtsTextRef.current)
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

            socketClient.on('interview_ended', (data: any) => {
                if (data?.session_id && sessionIdRef.current && data.session_id !== sessionIdRef.current) return
                console.log('Interview ended:', data)
                interviewStartedRef.current = false
                setInterviewStarted(false)
                sessionIdRef.current = ''
                currentTurnIdRef.current = ''
                interruptEpochRef.current = 0
                activeTtsJobIdRef.current = ''
                resetAnswerSessionUi()
                stopAudioRecording()

                // 创建自定义弹窗
                const modal = document.createElement('div')
                modal.className = 'fixed inset-0 bg-black/70 backdrop-blur-md flex items-center justify-center z-50 animate-fade-in p-4'
                modal.innerHTML = `
                    <div class="bg-gradient-to-br from-white via-blue-50 to-indigo-100 dark:from-gray-800 dark:via-gray-850 dark:to-gray-900 rounded-3xl shadow-2xl max-w-lg w-full mx-4 border-2 border-blue-200 dark:border-gray-600 animate-scale-up overflow-hidden">
                        <!-- 装饰性顶部 -->
                        <div class="h-2 bg-gradient-to-r from-green-400 via-blue-500 to-purple-600"></div>

                        <!-- 主要内容 -->
                        <div class="p-10">
                            <div class="text-center mb-8">
                                <!-- 成功图标 -->
                                <div class="relative inline-block mb-6">
                                    <div class="w-28 h-28 bg-gradient-to-br from-green-400 to-green-600 rounded-full mx-auto flex items-center justify-center shadow-2xl animate-bounce-slow">
                                        <svg class="w-16 h-16 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path>
                                        </svg>
                                    </div>
                                    <!-- 光环效果 -->
                                    <div class="absolute inset-0 w-28 h-28 mx-auto bg-green-400 rounded-full opacity-20 animate-ping"></div>
                                </div>

                                <!-- 标题 -->
                                <h3 class="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-purple-600 dark:from-blue-400 dark:to-purple-400 mb-3">
                                    分析完成！
                                </h3>
                                <p class="text-lg text-gray-600 dark:text-gray-400">本次会话洞察已生成</p>

                                <!-- 分隔线 -->
                                <div class="mt-6 mb-8 flex items-center justify-center gap-3">
                                    <div class="h-px w-16 bg-gradient-to-r from-transparent to-blue-400"></div>
                                    <div class="w-2 h-2 rounded-full bg-blue-400"></div>
                                    <div class="h-px w-16 bg-gradient-to-l from-transparent to-blue-400"></div>
                                </div>
                            </div>

                            <!-- 信息卡片 -->
                            <div class="bg-white dark:bg-gray-800 rounded-2xl p-6 mb-8 shadow-lg border border-gray-200 dark:border-gray-700">
                                <div class="flex items-center justify-center gap-4 text-center">
                                    <div class="flex-1">
                                        <div class="inline-flex items-center justify-center w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-full mb-2">
                                            <svg class="w-6 h-6 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                            </svg>
                                        </div>
                                        <p class="text-xs text-gray-500 dark:text-gray-400 font-semibold uppercase tracking-wide">状态</p>
                                        <p class="text-sm font-bold text-green-600 dark:text-green-400 mt-1">已完成</p>
                                    </div>
                                    <div class="w-px h-12 bg-gray-300 dark:bg-gray-600"></div>
                                    <div class="flex-1">
                                        <div class="inline-flex items-center justify-center w-12 h-12 bg-purple-100 dark:bg-purple-900/30 rounded-full mb-2">
                                            <svg class="w-6 h-6 text-purple-600 dark:text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                                            </svg>
                                        </div>
                                        <p class="text-xs text-gray-500 dark:text-gray-400 font-semibold uppercase tracking-wide">报告</p>
                                        <p class="text-sm font-bold text-purple-600 dark:text-purple-400 mt-1">报告已生成</p>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- 按钮 -->
                            <button 
                                onclick="this.closest('.fixed').remove(); window.location.href='/report'" 
                                class="group relative w-full bg-gradient-to-r from-blue-600 via-blue-500 to-indigo-600 hover:from-blue-700 hover:via-blue-600 hover:to-indigo-700 text-white font-bold py-5 px-8 rounded-2xl transition-all duration-300 transform hover:scale-105 shadow-2xl hover:shadow-blue-500/50 overflow-hidden"
                            >
                                <span class="relative z-10 flex items-center justify-center gap-3 text-lg">
                                    查看洞察
                                    <svg class="w-5 h-5 transform group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                                    </svg>
                                </span>
                                <!-- 动画光效 -->
                                <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent transform -skew-x-12 translate-x-full group-hover:translate-x-[-200%] transition-transform duration-1000"></div>
                            </button>
                        </div>
                    </div>
                `
                document.body.appendChild(modal)
            })
        } catch (error) {
            console.error('Socket connection error:', error)
            alert('Failed to connect to server')
            router.push('/')
        }
    }

    const handleStartInterview = () => {
        if (!socket) return

        socketRef.current = socket
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
        speechActiveRef.current = false
        clearSpeechPrebuffer()
        setServerAsrAvailability(true)
        resetAnswerSessionUi()
        interviewStartedRef.current = true
        setInterviewStarted(true)
        setChatMessages([])
        setCurrentQuestion('')
        setUserAnswer('')

        socket.emit('session_start', {
            session_id: sessionId,
            round_type: interviewConfig.round,
            position: interviewConfig.position,
            difficulty: interviewConfig.difficulty,
            user_id: 'default'
        })
    }

    const handleEndInterview = () => {
        if (!socket || !sessionIdRef.current) return
        clearLlmTimeout()
        clearPendingCommit()
        stopCurrentTts()
        stopAudioRecording()
        speechActiveRef.current = false
        clearSpeechPrebuffer()
        interviewStartedRef.current = false
        setInterviewStarted(false)
        resetAnswerSessionUi()
        socket.emit('session_end', { session_id: sessionIdRef.current })
        setUserAnswer('')
        socketRef.current = null
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
    const voiceStatusText = !voiceInputEnabled
        ? (isVoiceSupported
            ? '语音识别当前不可用，请使用下方文本框继续回答。'
            : '当前浏览器无法录音，请使用下方文本框回答。')
        : isAiSpeaking
            ? '面试官正在提问，请聆听...'
            : isProcessing
                ? '正在分析你的回答并生成下一问...'
                : answerSessionStatus === 'finalizing'
                    ? '当前回答整理中，正在生成终稿...'
                    : answerSessionStatus === 'paused_short'
                        ? '检测到短暂停顿，继续说话会自动并入同一题回答。'
                        : isListening
                            ? (isServerAsrAvailable
                                ? 'ASR 语音识别中，直接说话即可...'
                                : '浏览器语音识别中，直接说话即可...')
                            : (isServerAsrAvailable
                                ? 'ASR 识别服务已启动'
                                : '浏览器语音识别已启动')
    const answerPanelTitle = !voiceInputEnabled
        ? '你的回答'
        : answerSessionStatus === 'recording'
            ? '当前回答（实时识别中）'
            : answerSessionStatus === 'paused_short'
                ? '当前回答（短暂停顿）'
                : answerSessionStatus === 'finalizing'
                    ? '当前回答（整理中）'
                    : answerSessionStatus === 'finalized'
                        ? '最终回答'
                        : '你的回答'
    const answerPanelHint = !voiceInputEnabled
        ? '当前为文字回答模式'
        : answerSessionStatus === 'finalizing'
            ? '系统正在把同一题下的多个语音分段整理成完整回答'
            : answerSessionStatus === 'paused_short'
                ? '这一小段停顿不会提交给面试官，继续说会自动续写'
                : '语音转写会同步显示，可直接编辑后提交'

    useEffect(() => {
        if (!cameraReady || !socket || !interviewStarted || !sessionIdRef.current) return

        const emitDetectionState = () => {
            const now = Date.now()
            const hasFace = Boolean(rppgMetrics.hasFace)
            if (hasFace) {
                noFaceSinceRef.current = null
            } else if (noFaceSinceRef.current === null) {
                noFaceSinceRef.current = now
            }

            const noFaceLong = !hasFace && noFaceSinceRef.current !== null && now - noFaceSinceRef.current >= 3000
            const offScreen = hasFace ? 0 : 1
            const faceCount = hasFace ? 1 : 0

            let riskScore = 18
            if (!hasFace) {
                riskScore = noFaceLong ? 88 : 58
            } else if (rppgMetrics.status === 'unstable') {
                riskScore = 46
            } else if (rppgMetrics.status === 'error') {
                riskScore = 66
            } else if (!rppgMetrics.isReliable) {
                riskScore = 28
            } else if (rppgMetrics.hr !== null && (rppgMetrics.hr < 48 || rppgMetrics.hr > 125)) {
                riskScore = 52
            }

            const nextRiskLevel = riskScore >= 75 ? 'HIGH' : riskScore >= 40 ? 'MEDIUM' : 'LOW'
            const nextGazeStatus = hasFace ? 'Normal' : 'Face Missing'
            const nextMouthStatus = speechActiveRef.current ? 'Speaking' : 'Closed'
            const flags = [
                ...(noFaceLong ? ['no_face_long'] : []),
                ...(!hasFace ? ['face_missing'] : []),
                ...(rppgMetrics.status === 'error' ? ['sensor_error'] : []),
                ...(rppgMetrics.status === 'unstable' ? ['signal_unstable'] : []),
                ...(nextRiskLevel === 'HIGH' ? ['high_risk'] : [])
            ]

            socket.emit('detection_state', {
                session_id: sessionIdRef.current,
                ts: now,
                has_face: hasFace,
                face_count: faceCount,
                off_screen_ratio: offScreen,
                rppg_reliable: rppgMetrics.isReliable,
                hr: rppgMetrics.hr,
                risk_level: nextRiskLevel,
                risk_score: riskScore,
                gaze_status: nextGazeStatus,
                mouth_status: nextMouthStatus,
                flags
            })
        }

        emitDetectionState()
        const interval = setInterval(emitDetectionState, 250)

        return () => clearInterval(interval)
    }, [
        cameraReady,
        socket,
        interviewStarted,
        rppgMetrics.hasFace,
        rppgMetrics.hr,
        rppgMetrics.isReliable,
        rppgMetrics.status
    ])

    const getRppgStatusLabel = () => {
        if (rppgMetrics.status === 'loading') return '心率模型加载中'
        if (rppgMetrics.status === 'tracking') return '采集中'
        if (rppgMetrics.status === 'unstable') return '信号不稳定'
        if (rppgMetrics.status === 'no_face') return '未检测到人脸'
        if (rppgMetrics.status === 'error') return '心率初始化失败'
        return '等待开始'
    }

    const getRppgStatusClass = () => {
        if (rppgMetrics.status === 'tracking') return 'bg-emerald-500/20 text-emerald-200 border-emerald-400/40'
        if (rppgMetrics.status === 'unstable') return 'bg-amber-500/20 text-amber-100 border-amber-300/40'
        if (rppgMetrics.status === 'error') return 'bg-red-500/20 text-red-100 border-red-300/40'
        return 'bg-slate-800/70 text-slate-100 border-white/15'
    }

    const hrDisplay = rppgMetrics.isReliable && rppgMetrics.hr !== null
        ? rppgMetrics.hr.toFixed(1)
        : '--'
    const sqiDisplay = rppgMetrics.sqi !== null ? rppgMetrics.sqi.toFixed(2) : '--'
    const rppgHint = rppgMetrics.error
        || (rppgMetrics.fps !== null && rppgMetrics.latencyMs !== null
            ? `${rppgMetrics.fps.toFixed(1)} FPS · ${rppgMetrics.latencyMs.toFixed(1)} ms`
            : '本地设备实时计算，不上传视频或心率数据')

    if (interviewStarted) {
        return (
            <div className="min-h-screen bg-black">
                <div className="relative h-screen w-full overflow-hidden bg-black">
                    <video
                        ref={videoRef}
                        autoPlay
                        playsInline
                        muted
                        className="absolute inset-0 h-full w-full object-cover"
                    />

                    {!cameraReady && (
                        <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-gray-900 to-black">
                            <div className="text-center text-white">
                                <div className="relative">
                                    <div className="mx-auto mb-4 h-16 w-16 animate-spin rounded-full border-4 border-gray-700 border-t-blue-500"></div>
                                    <div className="absolute inset-0 flex items-center justify-center">
                                        <div className="h-8 w-8 animate-pulse rounded-full bg-blue-500"></div>
                                    </div>
                                </div>
                                <p className="text-lg font-semibold">加载摄像头中...</p>
                            </div>
                        </div>
                    )}

                    <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-transparent to-black/35"></div>
                    <div className="absolute left-3 top-3 z-20 flex items-center gap-3 sm:left-4 sm:top-4">
                        <div className="rounded-full border border-white/15 bg-slate-950/55 px-3 py-2 text-xs font-semibold tracking-[0.18em] text-white shadow-xl backdrop-blur-md">
                            AI 模拟面试舱
                        </div>
                        <div className="hidden rounded-full border border-red-400/25 bg-red-500/15 px-3 py-2 text-xs font-semibold text-red-100 shadow-xl backdrop-blur-md sm:flex sm:items-center sm:gap-2">
                            <span className="h-2 w-2 animate-pulse rounded-full bg-red-400"></span>
                            录制中
                        </div>
                    </div>

                    <div className="absolute right-3 top-3 z-20 flex items-center gap-2 sm:right-4 sm:top-4">
                        <button
                            onClick={() => router.push('/')}
                            className="flex items-center gap-2 rounded-full border border-white/15 bg-slate-950/55 px-3 py-2 text-sm font-medium text-white shadow-xl backdrop-blur-md transition hover:bg-slate-950/70"
                        >
                            <Home className="h-4 w-4" />
                            <span className="hidden sm:inline">首页</span>
                        </button>
                        <button
                            onClick={() => router.push('/report')}
                            className="flex items-center gap-2 rounded-full border border-white/15 bg-slate-950/55 px-3 py-2 text-sm font-medium text-white shadow-xl backdrop-blur-md transition hover:bg-slate-950/70"
                        >
                            <FileText className="h-4 w-4" />
                            <span className="hidden sm:inline">报告</span>
                        </button>
                        <button
                            onClick={handleEndInterview}
                            className="rounded-full bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-xl transition hover:bg-red-700"
                        >
                            结束面试
                        </button>
                    </div>

                    <div className="absolute left-1/2 top-3 z-20 w-[min(92vw,32rem)] -translate-x-1/2 sm:top-4">
                        <div className="rounded-[28px] border border-white/15 bg-slate-950/48 px-5 py-3 text-center text-white shadow-2xl backdrop-blur-md">
                            <p className="text-[11px] uppercase tracking-[0.28em] text-white/65">当前面试轮次</p>
                            <div className="mt-1 flex items-center justify-center gap-3">
                                <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/15 bg-white/10">
                                    <Radar className="h-5 w-5" />
                                </div>
                                <div>
                                    <h2 className="text-lg font-black sm:text-xl">{interviewConfig.roundName}</h2>
                                    <p className="text-xs text-white/65">
                                        {interviewConfig.position.replace('_', ' ')} · 难度：
                                        {interviewConfig.difficulty === 'easy' ? '简单' : interviewConfig.difficulty === 'medium' ? '中等' : '困难'}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="absolute bottom-3 left-3 right-3 z-20 flex max-h-[46vh] flex-col rounded-[30px] border border-white/12 bg-slate-950/36 p-4 text-white shadow-2xl backdrop-blur-md sm:left-auto sm:top-24 sm:right-4 sm:bottom-4 sm:max-h-none sm:w-[min(28rem,42vw)] lg:w-[min(30rem,34vw)]">
                        <h2 className="mb-4 flex items-center gap-2 text-lg font-bold">
                            <Mic className="h-5 w-5 text-cyan-300" />
                            面试对话
                        </h2>

                        <div
                            ref={chatScrollContainerRef}
                            className="mb-4 min-h-0 flex-1 overflow-y-auto overscroll-contain rounded-2xl border border-white/10 bg-black/18 p-4"
                        >
                            {chatMessages.length === 0 ? (
                                <p className="py-8 text-center text-sm text-white/60">等待面试官提问...</p>
                            ) : (
                                <div className="space-y-4">
                                    {chatMessages.map((msg, idx) => (
                                        <div
                                            key={idx}
                                            className={`flex ${msg.role === 'candidate' ? 'justify-end' : 'justify-start'}`}
                                        >
                                            <div
                                                className={`max-w-[90%] rounded-2xl px-4 py-3 ${msg.role === 'candidate'
                                                    ? 'bg-cyan-500/78 text-white'
                                                    : 'border border-white/10 bg-white/12 text-white'
                                                    }`}
                                            >
                                                <p className="mb-1 text-xs font-medium opacity-70">
                                                    {msg.role === 'candidate' ? '你' : '面试官'} · {msg.timestamp}
                                                </p>
                                                <p className="text-sm leading-relaxed">{msg.content}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div className="flex flex-col gap-3">
                            <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/10 px-4 py-3">
                                <Mic className={`h-5 w-5 ${voiceInputEnabled && isListening && answerSessionStatus !== 'finalizing' ? 'animate-pulse text-emerald-300' : voiceInputEnabled ? 'text-white/65' : 'text-amber-300'}`} />
                                <span className="text-sm text-white/80">
                                    {voiceStatusText}
                                </span>
                            </div>

                            {!voiceInputEnabled && (
                                <div className="rounded-2xl border border-amber-300/20 bg-amber-500/12 px-4 py-3 text-sm text-amber-100">
                                    {asrStatusMessage || '语音识别当前不可用，系统已切换到文字回答模式。'}
                                </div>
                            )}

                            <div className="rounded-2xl border border-white/10 bg-white/10 p-3">
                                <div className="mb-2 flex items-center justify-between gap-3">
                                    <p className="text-sm font-semibold text-white">{answerPanelTitle}</p>
                                    <p className="text-xs text-white/55">
                                        {answerPanelHint}
                                    </p>
                                </div>
                                <textarea
                                    value={userAnswer}
                                    onChange={(event) => setUserAnswer(event.target.value)}
                                    onKeyDown={(event) => {
                                        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                                            event.preventDefault()
                                            handleSubmitAnswer()
                                        }
                                    }}
                                    disabled={!currentQuestion || isProcessing || isAiSpeaking}
                                    placeholder={voiceInputEnabled
                                        ? '你可以直接说话，也可以在这里修改识别结果后提交。'
                                        : '请输入你的回答，然后点击“提交回答”。'}
                                    className="min-h-[112px] w-full resize-y rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm leading-6 text-white outline-none transition placeholder:text-white/35 focus:border-cyan-300/60 focus:bg-black/30 disabled:cursor-not-allowed disabled:opacity-60"
                                />
                                <div className="mt-3 flex items-center justify-between gap-3">
                                    <p className="text-xs text-white/50">
                                        `Ctrl/Cmd + Enter` 可快速提交
                                    </p>
                                    <button
                                        onClick={() => handleSubmitAnswer()}
                                        disabled={!userAnswer.trim() || !currentQuestion || isProcessing || isAiSpeaking}
                                        className="rounded-xl bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:bg-white/20 disabled:text-white/50"
                                    >
                                        提交回答
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="absolute bottom-4 left-4 z-20 hidden w-[300px] rounded-[28px] border border-white/12 bg-slate-950/42 p-4 text-white shadow-2xl backdrop-blur-md sm:block">
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <p className="text-[11px] uppercase tracking-[0.22em] text-cyan-200/70">FacePhys rPPG</p>
                                <h3 className="mt-1 text-sm font-semibold">本地心率监测</h3>
                            </div>
                            <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold ${getRppgStatusClass()}`}>
                                {getRppgStatusLabel()}
                            </span>
                        </div>

                        <div className="mt-4 grid grid-cols-2 gap-3">
                            <div className="rounded-2xl border border-white/10 bg-white/10 px-3 py-3">
                                <p className="text-[11px] uppercase tracking-[0.18em] text-white/55">心率 BPM</p>
                                <p className="mt-2 text-3xl font-black text-white">{hrDisplay}</p>
                            </div>
                            <div className="rounded-2xl border border-white/10 bg-white/10 px-3 py-3">
                                <p className="text-[11px] uppercase tracking-[0.18em] text-white/55">SQI</p>
                                <p className="mt-2 text-3xl font-black text-white">{sqiDisplay}</p>
                            </div>
                        </div>

                        <div className="mt-3 rounded-2xl border border-white/10 bg-white/10 px-3 py-3">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-white/55">信号状态</p>
                            <p className="mt-2 text-sm font-medium text-white">
                                {rppgMetrics.hasFace ? '人脸跟踪中' : '等待稳定人脸进入画面'}
                            </p>
                            <p className="mt-2 text-xs leading-5 text-white/62">{rppgHint}</p>
                        </div>
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-gray-50 p-4 transition-colors dark:bg-gray-900">
            <div className="mx-auto max-w-7xl">
                <div className="mb-4 animate-slide-up rounded-lg bg-white p-4 shadow-md dark:bg-gray-800">
                    <div className="flex items-center justify-between">
                        <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100">AI 模拟面试舱</h1>
                        <div className="flex gap-4">
                            <button
                                onClick={() => router.push('/')}
                                className="flex items-center gap-2 rounded-lg bg-gray-500 px-4 py-2 font-semibold text-white shadow-lg transition hover:bg-gray-600 hover:shadow-xl"
                            >
                                <Home className="h-5 w-5" />
                                首页
                            </button>
                            <button
                                onClick={() => router.push('/report')}
                                className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 font-semibold text-white shadow-lg transition hover:bg-blue-600 hover:shadow-xl"
                            >
                                <FileText className="h-5 w-5" />
                                报告
                            </button>
                            <button
                                onClick={handleStartInterview}
                                disabled={!cameraReady}
                                className="rounded-lg bg-green-600 px-6 py-2 font-semibold text-white shadow-lg transition hover:bg-green-700 hover:shadow-xl disabled:bg-gray-400 dark:disabled:bg-gray-600"
                            >
                                开始面试
                            </button>
                        </div>
                    </div>
                </div>

                <div className="space-y-6">
                    <div className="animate-fade-in rounded-2xl border border-gray-100 bg-gradient-to-br from-white to-gray-50 p-6 shadow-2xl dark:border-gray-700 dark:from-gray-800 dark:to-gray-900">
                        <div className="mb-4 flex items-center justify-between">
                            <h2 className="flex items-center gap-2 text-xl font-bold text-gray-800 dark:text-gray-100">
                                <div className="h-2 w-2 animate-pulse rounded-full bg-red-500"></div>
                                实时画面
                            </h2>
                            <div className="rounded-full border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-semibold text-indigo-700 dark:border-indigo-500/20 dark:bg-indigo-500/10 dark:text-indigo-200">
                                {interviewConfig.roundName}
                            </div>
                        </div>
                        <div className="relative h-[64vh] min-h-[420px] overflow-hidden rounded-xl border-4 border-gray-200 bg-gradient-to-br from-gray-900 to-black shadow-2xl dark:border-gray-700">
                            <video
                                ref={videoRef}
                                autoPlay
                                playsInline
                                muted
                                className="h-full w-full object-cover"
                            />
                            {!cameraReady && (
                                <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-gray-900 to-black">
                                    <div className="text-center text-white">
                                        <div className="relative">
                                            <div className="mx-auto mb-4 h-16 w-16 animate-spin rounded-full border-4 border-gray-700 border-t-blue-500"></div>
                                            <div className="absolute inset-0 flex items-center justify-center">
                                                <div className="h-8 w-8 animate-pulse rounded-full bg-blue-500"></div>
                                            </div>
                                        </div>
                                        <p className="text-lg font-semibold">加载摄像头中...</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

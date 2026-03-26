'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import SocketClient from '@/lib/socket'
import { useFacePhysRppg } from '@/lib/facephys/useFacePhysRppg'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { AlertTriangle, Home, FileText, Mic, Radar } from 'lucide-react'

interface HistoryData {
    time: string
    probability: number
}

interface ChatMessage {
    role: 'interviewer' | 'candidate'
    content: string
    timestamp: string
}

export default function InterviewPage() {
    const router = useRouter()
    const videoRef = useRef<HTMLVideoElement>(null)
    const canvasRef = useRef<HTMLCanvasElement>(null)
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
    const [isProcessing, setIsProcessing] = useState(false)
    const [isVoiceSupported, setIsVoiceSupported] = useState(true)
    const [isListening, setIsListening] = useState(false)
    const [isAiSpeaking, setIsAiSpeaking] = useState(false)
    const [isRecording, setIsRecording] = useState(false)

    // 检测数据
    const [probability, setProbability] = useState(0)
    const [riskLevel, setRiskLevel] = useState('LOW')
    const [riskColor, setRiskColor] = useState('green')
    const [gazeStatus, setGazeStatus] = useState('Normal')
    const [mouthStatus, setMouthStatus] = useState('Closed')
    const [numFaces, setNumFaces] = useState(0)
    const [offScreenRatio, setOffScreenRatio] = useState(0)

    // 历史数据 - 用于图表
    const [historyData, setHistoryData] = useState<HistoryData[]>([])
    const [showAlert, setShowAlert] = useState(false)
    const interviewStartedRef = useRef(false)
    const isAiSpeakingRef = useRef(false)
    const isProcessingRef = useRef(false)
    const isRecordingRef = useRef(false)
    const lastSubmittedRef = useRef<{ text: string; at: number }>({ text: '', at: 0 })
    const llmTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const audioContextRef = useRef<AudioContext | null>(null)
    const audioWorkletNodeRef = useRef<AudioWorkletNode | null>(null)
    const socketRef = useRef<SocketClient | null>(null)
    // TTS 音频播放
    const ttsAudioContextRef = useRef<AudioContext | null>(null)
    const ttsSourceNodeRef = useRef<AudioBufferSourceNode | null>(null)
    const ttsAudioQueueRef = useRef<Float32Array[]>([])
    const isTTSSpeakingRef = useRef(false)
    const ttsChunkReceivedRef = useRef(false)
    const ttsSafetyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const firstQuestionReadyRef = useRef(false)
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

    useEffect(() => {
        interviewStartedRef.current = interviewStarted
    }, [interviewStarted])

    useEffect(() => {
        isAiSpeakingRef.current = isAiSpeaking
    }, [isAiSpeaking])

    useEffect(() => {
        isProcessingRef.current = isProcessing
    }, [isProcessing])

    useEffect(() => {
        isRecordingRef.current = isRecording
    }, [isRecording])

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
            cleanupAudioRecording()
            stopCamera()
            if (socket) {
                socket.emit('end_interview')
                socket.disconnect()
            }
        }
    }, [])

    const initCamera = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480 }
            })

            if (videoRef.current) {
                videoRef.current.srcObject = stream
                setCameraReady(true)
            }
        } catch (error) {
            console.error('Camera error:', error)
            alert('Camera access denied')
            router.push('/')
        }
    }

    const stopCamera = () => {
        if (videoRef.current && videoRef.current.srcObject) {
            const stream = videoRef.current.srcObject as MediaStream
            stream.getTracks().forEach(track => track.stop())
        }
    }

    const submitRecognizedAnswer = (rawText: string) => {
        const normalized = (rawText || '').trim().replace(/\s+/g, ' ')
        if (!normalized) return

        const now = Date.now()
        const isDuplicate =
            normalized === lastSubmittedRef.current.text
            && now - lastSubmittedRef.current.at < 2500

        if (isDuplicate) return

        lastSubmittedRef.current = { text: normalized, at: now }
        handleSubmitAnswer(normalized)
    }

    const speakText = (text: string) => {
        // 仅用于准备 TTS 播放状态，实际音频由后端 Edge TTS 合成并通过 Socket 下发
        if (!text || !text.trim()) return

        stopAudioRecording()
        setIsAiSpeaking(true)
        isTTSSpeakingRef.current = true
        ttsChunkReceivedRef.current = false
        clearTtsTimers()

        // 10 秒超时保护：若 TTS 一直未完成，自动恢复录音
        ttsSafetyTimerRef.current = setTimeout(() => {
            if (isTTSSpeakingRef.current) {
                console.warn('[TTS] 超时未收到音频，恢复录音')
                clearTtsTimers()
                isTTSSpeakingRef.current = false
                isAiSpeakingRef.current = false
                setIsAiSpeaking(false)
                if (interviewStartedRef.current) {
                    startAudioRecording()
                }
            }
        }, 10000)
    }

    const playTTSAudio = (base64Audio: string) => {
        try {
            console.log('[TTS] 开始播放音频')
            ttsChunkReceivedRef.current = true

            // 将 Base64 转为 Blob（MP3 格式）
            const binaryString = atob(base64Audio)
            const len = binaryString.length
            const bytes = new Uint8Array(len)
            for (let i = 0; i < len; i++) {
                bytes[i] = binaryString.charCodeAt(i)
            }

            const blob = new Blob([bytes], { type: 'audio/mpeg' })
            const url = URL.createObjectURL(blob)

            // 创建 Audio 元素播放
            const audio = new Audio()
            audio.src = url
            audio.onended = () => {
                console.log('[TTS] 播放完成')
                URL.revokeObjectURL(url)
                clearTtsTimers()
                isTTSSpeakingRef.current = false
                isAiSpeakingRef.current = false
                setIsAiSpeaking(false)
                if (interviewStartedRef.current) {
                    startAudioRecording()
                }
            }
            audio.onerror = (error) => {
                console.error('[TTS] 播放错误:', error)
                URL.revokeObjectURL(url)
                clearTtsTimers()
                isTTSSpeakingRef.current = false
                isAiSpeakingRef.current = false
                setIsAiSpeaking(false)
                if (interviewStartedRef.current) {
                    startAudioRecording()
                }
            }

            audio.play().catch((err) => {
                console.error('[TTS] 播放失败:', err)
                URL.revokeObjectURL(url)
                clearTtsTimers()
                isTTSSpeakingRef.current = false
                isAiSpeakingRef.current = false
                setIsAiSpeaking(false)
                if (interviewStartedRef.current) {
                    startAudioRecording()
                }
            })
        } catch (error) {
            console.error('[TTS] 播放异常:', error)
            clearTtsTimers()
            isTTSSpeakingRef.current = false
            isAiSpeakingRef.current = false
            setIsAiSpeaking(false)
            if (interviewStartedRef.current) {
                startAudioRecording()
            }
        }
    }

    const cleanTextForSpeech = (text: string): string => {
        let cleaned = text

        // 1. 移除代码块 ```xxx```
        cleaned = cleaned.replace(/```[\s\S]*?```/g, ' 代码示例 ')

        // 2. 移除行内代码 `xxx`
        cleaned = cleaned.replace(/`([^`]+)`/g, ' $1 ')

        // 3. 移除 Markdown 标题 ### xxx -> xxx
        cleaned = cleaned.replace(/^#{1,6}\s+/gm, '')

        // 4. 移除加粗 **xxx** -> xxx
        cleaned = cleaned.replace(/\*\*([^*]+)\*\*/g, '$1')

        // 5. 移除斜体 *xxx* -> xxx
        cleaned = cleaned.replace(/\*([^*]+)\*/g, '$1')

        // 6. 移除链接 [xxx](url) -> xxx
        cleaned = cleaned.replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1')

        // 7. 移除图片 ![](url)
        cleaned = cleaned.replace(/!\[([^\]]*)\]\([^\)]+\)/g, '$1')

        // 8. 移除列表符号 - xxx -> xxx
        cleaned = cleaned.replace(/^[\-\*+]\s+/gm, '')

        // 9. 移除引用符号 > xxx -> xxx
        cleaned = cleaned.replace(/^>\s+/gm, '')

        // 10. 清理多余空格
        cleaned = cleaned.replace(/\s+/g, ' ').trim()

        return cleaned
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

                if (!socketRef.current || !isRecordingRef.current || !interviewStartedRef.current || isAiSpeakingRef.current) {
                    return
                }

                if (event.data instanceof ArrayBuffer) {
                    const pcmData = event.data
                    const base64Audio = arrayBufferToBase64(pcmData)
                    socketRef.current.emit('audio_stream', {
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
        if (!audioWorkletNodeRef.current) {
            console.warn('[ASR] audioWorkletNodeRef 为空')
            return
        }
        if (!interviewStartedRef.current) {
            console.warn('[ASR] interviewStartedRef 为 false')
            return
        }
        if (isAiSpeakingRef.current) {
            console.warn('[ASR] isAiSpeakingRef 为 true，等待播放完成')
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

            // 避免开发模式下重复注册同名事件监听器
            socketClient.off('interview_started')
            socketClient.off('llm_answer')
            socketClient.off('error')
            socketClient.off('asr_error')
            socketClient.off('detection_result')
            socketClient.off('asr_result')
            socketClient.off('asr_started')
            socketClient.off('tts_audio')
            socketClient.off('tts_error')
            socketClient.off('interview_ended')

            socketClient.on('interview_started', (data: any) => {
                console.log('Interview started:', data)
                // 显示第一个问题
                if (data.question) {
                    firstQuestionReadyRef.current = true
                    setCurrentQuestion(data.question)
                    speakText(data.question)
                    setChatMessages(prev => [{
                        role: 'interviewer',
                        content: data.question,
                        timestamp: new Date().toLocaleTimeString()
                    }])
                }
            })

            socketClient.on('llm_answer', (data: any) => {
                console.log('LLM answer:', data)
                clearLlmTimeout()
                // 更新当前问题或追问
                if (data.feedback) {
                    setCurrentQuestion(data.feedback)
                    speakText(data.feedback)
                    setChatMessages(prev => [...prev, {
                        role: 'interviewer',
                        content: data.feedback,
                        timestamp: new Date().toLocaleTimeString()
                    }])
                    setIsProcessing(false)
                }
            })

            socketClient.on('error', (data: any) => {
                console.error('[Interview] 后端错误:', data)
                clearLlmTimeout()
                setIsProcessing(false)
            })

            socketClient.on('asr_error', (data: any) => {
                console.error('[ASR] 错误:', data)
                clearLlmTimeout()
                setIsProcessing(false)
            })

            socketClient.on('detection_result', (data: any) => {
                const prob = data.probability || 0
                setProbability(prob)
                setRiskLevel(data.risk_level || 'LOW')
                setRiskColor(data.risk_color || 'green')
                setGazeStatus(data.gaze_status || 'Normal')
                setMouthStatus(data.mouth_status || 'Closed')
                setNumFaces(data.num_faces || 0)
                setOffScreenRatio(data.off_screen_ratio || 0)

                // 添加到历史数据
                const now = new Date()
                const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`

                setHistoryData(prev => {
                    const newData = [...prev, { time: timeStr, probability: prob }]
                    // 只保留最近60个数据点
                    return newData.slice(-60)
                })

                // 高风险警告
                if (prob > 60 && !showAlert) {
                    setShowAlert(true)
                    setTimeout(() => setShowAlert(false), 3000)
                }
            })

            // ASR 识别结果 - 阿里 DashScope ASR
            socketClient.on('asr_result', (data: any) => {
                if (data.success && data.text) {
                    console.log('[ASR] 识别结果:', data.text)
                    // 后端已做 ASR->LLM 兜底处理，这里仅用于前端展示
                    setUserAnswer(data.text)
                }
            })

            socketClient.on('asr_started', (data: any) => {
                console.log('[ASR] ASR 已启动', data)
                console.log('[ASR] interviewStartedRef.current:', interviewStartedRef.current)
                console.log('[ASR] isAiSpeakingRef.current:', isAiSpeakingRef.current)
                console.log('[ASR] audioWorkletNodeRef.current:', audioWorkletNodeRef.current)
                // 首个问题语音播报前不立刻开录，避免“开始后马上停止”的闪烁
                if (!firstQuestionReadyRef.current) {
                    console.log('[ASR] 等待首个问题下发后再开启录音')
                    return
                }

                if (!isAiSpeakingRef.current && !isTTSSpeakingRef.current) {
                    startAudioRecording()
                }
            })

            // TTS 音频流播放 - Edge TTS
            socketClient.on('tts_audio', (data: any) => {
                if (data.audio) {
                    ttsChunkReceivedRef.current = true
                    console.log('[TTS] 收到音频数据，长度:', data.audio.length)
                    // 清除超时保护（已收到音频）
                    if (ttsSafetyTimerRef.current) {
                        clearTimeout(ttsSafetyTimerRef.current)
                        ttsSafetyTimerRef.current = null
                    }
                    playTTSAudio(data.audio)
                }
            })

            socketClient.on('tts_error', (data: any) => {
                // 打印原始数据，便于诊断
                console.log('[TTS] 原始错误数据:', data, 'type:', typeof data)
                const details = data?.details || data?.error || 'unknown tts error'
                console.error('[TTS] 后端错误:', {
                    code: data?.code || 'UNKNOWN',
                    details,
                    error: data?.error || 'N/A',
                    raw: data
                })
                clearTtsTimers()
                isTTSSpeakingRef.current = false
                isAiSpeakingRef.current = false
                setIsAiSpeaking(false)
                if (interviewStartedRef.current) {
                    startAudioRecording()
                }
            })

            socketClient.on('interview_ended', (data: any) => {
                console.log('Interview ended:', data)
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
        if (!isVoiceSupported) {
            alert('当前浏览器不支持语音录制，请确保使用最新版浏览器。')
            return
        }

        // 保存 socket 引用供音频处理使用
        socketRef.current = socket
        firstQuestionReadyRef.current = false

        // 先设置状态，确保 interviewStartedRef.current 为 true
        interviewStartedRef.current = true
        setInterviewStarted(true)
        setHistoryData([]) // 重置历史数据

        // 发送面试配置到后端
        socket.emit('start_interview', {
            round_type: interviewConfig.round,
            position: interviewConfig.position,
            difficulty: interviewConfig.difficulty
        })

        // 启动 ASR 服务
        socket.emit('start_asr')
    }

    const handleEndInterview = () => {
        if (!socket) return
        stopAudioRecording()
        socket.emit('stop_asr')
        setUserAnswer('')
        socket.emit('end_interview')
        socketRef.current = null
    }

    const handleSubmitAnswer = (forcedAnswer?: string) => {
        const answerText = (forcedAnswer ?? userAnswer).trim()
        const questionText = (currentQuestion || '').trim()
        if (!socket || !answerText || isProcessing || !questionText) {
            if (!questionText && answerText) {
                console.warn('[LLM] 当前还没有有效问题，跳过本次回答提交')
            }
            return
        }

        clearLlmTimeout()
        setIsProcessing(true)

        // 添加用户回答到聊天记录
        setChatMessages(prev => [...prev, {
            role: 'candidate',
            content: answerText,
            timestamp: new Date().toLocaleTimeString()
        }])

        // 发送回答到后端处理
        socket.emit('llm_process_answer', {
            user_answer: answerText,
            current_question: questionText,
            round_type: interviewConfig.round,
            position: interviewConfig.position,
            difficulty: interviewConfig.difficulty
        })

        llmTimeoutRef.current = setTimeout(() => {
            console.warn('[LLM] 处理超时，自动解除处理中状态')
            setIsProcessing(false)
        }, 15000)

        setUserAnswer('')
    }

    useEffect(() => {
        if (!cameraReady || !socket || !interviewStarted) return

        const interval = setInterval(() => {
            captureAndSend()
        }, 50) // 20 fps

        return () => clearInterval(interval)
    }, [cameraReady, socket, interviewStarted])

    const captureAndSend = () => {
        if (!videoRef.current || !canvasRef.current || !socket) return

        const video = videoRef.current
        const canvas = canvasRef.current
        const ctx = canvas.getContext('2d')

        if (!ctx) return

        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        ctx.drawImage(video, 0, 0)

        const frame = canvas.toDataURL('image/jpeg', 0.8)
        socket.emit('process_frame', { frame })
    }

    const getRiskColorClass = () => {
        if (riskColor === 'green') return 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/30 border-green-200 dark:border-green-800'
        if (riskColor === 'yellow') return 'text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/30 border-yellow-200 dark:border-yellow-800'
        return 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-800'
    }

    const getStrokeColor = () => {
        if (riskColor === 'green') return '#10b981'
        if (riskColor === 'yellow') return '#f59e0b'
        return '#ef4444'
    }

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

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-4 transition-colors">
            {/* High Risk Alert */}
            {showAlert && (
                <div className="fixed top-20 left-1/2 transform -translate-x-1/2 z-50 animate-shake">
                    <div className="bg-red-600 text-white px-6 py-4 rounded-lg shadow-2xl flex items-center gap-3">
                        <AlertTriangle className="w-6 h-6 animate-pulse" />
                        <div>
                            <p className="font-bold text-lg">⚠️ 风险波动提醒</p>
                            <p className="text-sm">检测到异常行为片段</p>
                        </div>
                    </div>
                </div>
            )}

            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 mb-4 animate-slide-up">
                    <div className="flex justify-between items-center">
                        <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100">AI 模拟面试舱</h1>
                        <div className="flex gap-4">
                            <button
                                onClick={() => router.push('/')}
                                className="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded-lg font-semibold transition shadow-lg hover:shadow-xl transform hover:scale-105 flex items-center gap-2"
                            >
                                <Home className="w-5 h-5" />
                                首页
                            </button>
                            <button
                                onClick={() => router.push('/report')}
                                className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg font-semibold transition shadow-lg hover:shadow-xl transform hover:scale-105 flex items-center gap-2"
                            >
                                <FileText className="w-5 h-5" />
                                报告
                            </button>
                            {!interviewStarted ? (
                                <button
                                    onClick={handleStartInterview}
                                    disabled={!cameraReady}
                                    className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 dark:disabled:bg-gray-600 text-white px-6 py-2 rounded-lg font-semibold transition shadow-lg hover:shadow-xl transform hover:scale-105"
                                >
                                    开始面试
                                </button>
                            ) : (
                                <button
                                    onClick={handleEndInterview}
                                    className="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-lg font-semibold transition shadow-lg hover:shadow-xl transform hover:scale-105"
                                >
                                    结束面试
                                </button>
                            )}
                        </div>
                    </div>
                </div>

                <div className={interviewStarted ? 'grid lg:grid-cols-[1.55fr_1fr] gap-6 items-stretch lg:min-h-[calc(100vh-190px)]' : 'space-y-6'}>
                    {/* Left: Interview Main Area */}
                    <div className="space-y-6 lg:h-full">
                        <div className="bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-900 rounded-2xl shadow-2xl p-6 animate-fade-in border border-gray-100 dark:border-gray-700 lg:h-full flex flex-col">
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 flex items-center gap-2">
                                    <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></div>
                                    实时画面
                                </h2>
                                {interviewStarted && (
                                    <span className="px-3 py-1 bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 rounded-full text-xs font-bold flex items-center gap-2">
                                        <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
                                        录制中
                                    </span>
                                )}
                            </div>
                            <div className="relative bg-gradient-to-br from-gray-900 to-black rounded-xl overflow-hidden shadow-2xl border-4 border-gray-200 dark:border-gray-700 h-[56vh] min-h-[420px] lg:h-auto lg:flex-1">
                                <video
                                    ref={videoRef}
                                    autoPlay
                                    playsInline
                                    muted
                                    className="w-full h-full object-cover"
                                />
                                <canvas ref={canvasRef} className="hidden" />

                                {!cameraReady && (
                                    <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-gray-900 to-black">
                                        <div className="text-white text-center">
                                            <div className="relative">
                                                <div className="animate-spin rounded-full h-16 w-16 border-4 border-gray-700 border-t-blue-500 mx-auto mb-4"></div>
                                                <div className="absolute inset-0 flex items-center justify-center">
                                                    <div className="w-8 h-8 bg-blue-500 rounded-full animate-pulse"></div>
                                                </div>
                                            </div>
                                            <p className="text-lg font-semibold">加载摄像头中...</p>
                                        </div>
                                    </div>
                                )}

                                {/* Risk Level Overlay */}
                                {interviewStarted && riskLevel === 'HIGH' && (
                                    <div className="absolute inset-0 border-4 border-red-500 rounded-xl animate-pulse pointer-events-none shadow-2xl"></div>
                                )}

                                {/* Corner Indicators */}
                                {interviewStarted && (
                                    <>
                                        <div className="absolute top-4 right-4 w-[280px] rounded-2xl border border-white/10 bg-slate-950/72 p-4 text-white shadow-2xl backdrop-blur-md pointer-events-none">
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
                                                <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-3">
                                                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-300">心率 BPM</p>
                                                    <p className="mt-2 text-3xl font-black text-white">{hrDisplay}</p>
                                                </div>
                                                <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-3">
                                                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-300">SQI</p>
                                                    <p className="mt-2 text-3xl font-black text-white">{sqiDisplay}</p>
                                                </div>
                                            </div>

                                            <div className="mt-3 rounded-xl border border-white/10 bg-white/5 px-3 py-3">
                                                <p className="text-[11px] uppercase tracking-[0.18em] text-slate-300">信号状态</p>
                                                <p className="mt-2 text-sm font-medium text-slate-100">
                                                    {rppgMetrics.hasFace ? '人脸跟踪中' : '等待稳定人脸进入画面'}
                                                </p>
                                                <p className="mt-2 text-xs leading-5 text-slate-300">{rppgHint}</p>
                                            </div>
                                        </div>

                                        <div className="absolute top-2 left-2 w-6 h-6 border-t-2 border-l-2 border-blue-400 rounded-tl-lg"></div>
                                        <div className="absolute top-2 right-2 w-6 h-6 border-t-2 border-r-2 border-blue-400 rounded-tr-lg"></div>
                                        <div className="absolute bottom-2 left-2 w-6 h-6 border-b-2 border-l-2 border-blue-400 rounded-bl-lg"></div>
                                        <div className="absolute bottom-2 right-2 w-6 h-6 border-b-2 border-r-2 border-blue-400 rounded-br-lg"></div>
                                    </>
                                )}
                            </div>
                        </div>

                        {/* Real-time Chart */}
                        {interviewStarted && historyData.length > 0 && (
                            <div className="bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-900 rounded-2xl shadow-2xl p-6 animate-slide-up border border-gray-100 dark:border-gray-700">
                                <h2 className="text-xl font-bold mb-4 text-gray-800 dark:text-gray-100 flex items-center gap-2">
                                    <svg className="w-5 h-5 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
                                    </svg>
                                    面试风险趋势
                                </h2>
                                <ResponsiveContainer width="100%" height={200}>
                                    <LineChart data={historyData}>
                                        <defs>
                                            <linearGradient id="colorProb" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor={getStrokeColor()} stopOpacity={0.3} />
                                                <stop offset="95%" stopColor={getStrokeColor()} stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
                                        <XAxis
                                            dataKey="time"
                                            stroke="#9ca3af"
                                            tick={{ fill: '#9ca3af', fontSize: 12 }}
                                            tickLine={{ stroke: '#9ca3af' }}
                                        />
                                        <YAxis
                                            domain={[0, 100]}
                                            stroke="#9ca3af"
                                            tick={{ fill: '#9ca3af', fontSize: 12 }}
                                            tickLine={{ stroke: '#9ca3af' }}
                                        />
                                        <Tooltip
                                            contentStyle={{
                                                backgroundColor: '#1f2937',
                                                border: '2px solid #4f46e5',
                                                borderRadius: '12px',
                                                color: '#fff',
                                                boxShadow: '0 10px 40px rgba(0,0,0,0.3)'
                                            }}
                                            labelStyle={{ color: '#9ca3af', fontWeight: 'bold' }}
                                        />
                                        <Legend
                                            wrapperStyle={{ color: '#9ca3af', paddingTop: '10px' }}
                                            iconType="circle"
                                        />
                                        <Line
                                            type="monotone"
                                            dataKey="probability"
                                            stroke={getStrokeColor()}
                                            strokeWidth={3}
                                            dot={{ fill: getStrokeColor(), strokeWidth: 2, r: 4 }}
                                            activeDot={{ r: 6, strokeWidth: 2 }}
                                            name="风险指数 %"
                                            fill="url(#colorProb)"
                                        />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        )}
                    </div>

                    {/* Right: Interview Chat */}
                    {interviewStarted && (
                        <div className="flex h-full flex-col gap-6">
                            {/* Current Round Info */}
                            <div className="bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 rounded-2xl shadow-2xl p-6 animate-fade-in text-white">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-4">
                                        <div className="w-16 h-16 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center">
                                            <Radar className="w-8 h-8" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium text-white/80">当前面试轮次</p>
                                            <h2 className="text-2xl font-black">{interviewConfig.roundName}</h2>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-sm font-medium text-white/80">面试职位</p>
                                        <p className="text-xl font-bold capitalize">{interviewConfig.position.replace('_', ' ')}</p>
                                        <p className="text-xs text-white/60 mt-1">难度：{interviewConfig.difficulty === 'easy' ? '简单' : interviewConfig.difficulty === 'medium' ? '中等' : '困难'}</p>
                                    </div>
                                </div>
                            </div>

                            <div className="bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-900 rounded-2xl shadow-2xl p-6 animate-slide-up border border-gray-100 dark:border-gray-700 flex-1 min-h-0 flex flex-col">
                                <h2 className="text-xl font-bold mb-4 text-gray-800 dark:text-gray-100 flex items-center gap-2">
                                    <Mic className="w-5 h-5 text-indigo-500" />
                                    面试对话
                                </h2>

                                {/* Message List */}
                                <div className="flex-1 overflow-y-auto mb-4 p-4 bg-gray-50 dark:bg-gray-900/50 rounded-xl border border-gray-200 dark:border-gray-700 min-h-[280px]">
                                    {chatMessages.length === 0 ? (
                                        <p className="text-center text-gray-500 dark:text-gray-400 py-8">等待面试官提问...</p>
                                    ) : (
                                        <div className="space-y-4">
                                            {chatMessages.map((msg, idx) => (
                                                <div
                                                    key={idx}
                                                    className={`flex ${msg.role === 'candidate' ? 'justify-end' : 'justify-start'}`}
                                                >
                                                    <div
                                                        className={`max-w-[88%] rounded-2xl px-4 py-3 ${msg.role === 'candidate'
                                                            ? 'bg-gradient-to-r from-indigo-500 to-purple-500 text-white'
                                                            : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700'
                                                            }`}
                                                    >
                                                        <p className="text-xs font-medium mb-1 opacity-70">
                                                            {msg.role === 'candidate' ? '你' : '面试官'} · {msg.timestamp}
                                                        </p>
                                                        <p className="text-sm leading-relaxed">{msg.content}</p>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                {/* Voice Interaction Status */}
                                <div className="flex flex-col gap-2">
                                    <div className="flex items-center gap-3 px-4 py-3 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800">
                                        <Mic className={`w-5 h-5 ${isListening ? 'text-green-500 animate-pulse' : 'text-gray-400'}`} />
                                        <span className="text-sm text-gray-700 dark:text-gray-300">
                                            {isAiSpeaking
                                                ? '面试官正在提问，请聆听...'
                                                : isProcessing
                                                    ? '正在分析你的回答并生成下一问...'
                                                    : isListening
                                                        ? 'ASR 语音识别中，直接说话即可...'
                                                        : 'ASR 识别服务已启动'}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                </div>
            </div>
        </div>
    )
}

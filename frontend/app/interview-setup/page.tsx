'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Camera, Mic, Settings2, CheckCircle2, AlertCircle, Play, Briefcase, Code, Building2, User, ArrowLeft } from 'lucide-react'
import { motion } from 'motion/react'
import { getBackendBaseUrl } from '@/lib/backend'

const BACKEND_API_BASE = getBackendBaseUrl()

const INTERVIEW_ROUNDS = [
    {
        id: 'technical',
        name: '技术基础面',
        description: '考察基础知识、编码能力、语言特性、框架原理',
        icon: Code
    },
    {
        id: 'project',
        name: '项目深度面',
        description: '考察项目经验、技术深度、问题解决能力',
        icon: Building2
    },
    {
        id: 'system_design',
        name: '系统设计面',
        description: '考察架构能力、全局思维、技术权衡能力',
        icon: Briefcase
    },
    {
        id: 'hr',
        name: 'HR 综合面',
        description: '考察软技能、文化匹配、职业规划',
        icon: User
    }
]

const POSITIONS = [
    { id: 'java_backend', name: 'Java 后端工程师' },
    { id: 'frontend', name: '前端工程师' },
    { id: 'test_engineer', name: '软件测试工程师' },
    { id: 'agent_developer', name: 'Agent开发工程师' },
    { id: 'product_manager', name: '产品经理' },
    { id: 'algorithm', name: '算法工程师' }
]

const DIFFICULTY_LEVELS = [
    { id: 'easy', name: '简单', description: '适合初级/应届生' },
    { id: 'medium', name: '中等', description: '适合 1-3 年经验' },
    { id: 'hard', name: '困难', description: '适合 3 年以上经验' }
]

export default function InterviewSetupPage() {
    const router = useRouter()
    const videoRef = useRef<HTMLVideoElement | null>(null)
    const streamRef = useRef<MediaStream | null>(null)

    const [selectedRound, setSelectedRound] = useState<string>('technical')
    const [selectedPosition, setSelectedPosition] = useState<string>('java_backend')
    const [selectedDifficulty, setSelectedDifficulty] = useState<string>('medium')
    const [selectedInterviewMode, setSelectedInterviewMode] = useState<'realistic_mock' | 'focused_training'>('realistic_mock')
    const [isStarting, setIsStarting] = useState(false)

    const [cameraStatus, setCameraStatus] = useState<'checking' | 'ok' | 'error'>('checking')
    const [micStatus, setMicStatus] = useState<'checking' | 'ok' | 'error'>('checking')
    const [serviceWarmupStatus, setServiceWarmupStatus] = useState<'idle' | 'warming' | 'ready' | 'error'>('idle')
    const [serviceWarmupText, setServiceWarmupText] = useState('正在预热服务...')

    const bindCameraPreview = useCallback(async () => {
        const videoEl = videoRef.current
        const stream = streamRef.current
        if (!videoEl || !stream) {
            return
        }

        if (videoEl.srcObject !== stream) {
            videoEl.srcObject = stream
        }

        try {
            await videoEl.play()
        } catch (error) {
            console.warn('camera preview play interrupted:', error)
        }
    }, [])

    useEffect(() => {
        let mounted = true

        const initDevices = async () => {
            let localVideoStream: MediaStream | null = null

            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
                })
                localVideoStream = stream
                if (!mounted) {
                    stream.getTracks().forEach((track) => track.stop())
                    return
                }
                streamRef.current = stream
                void bindCameraPreview()
                setCameraStatus('ok')
            } catch (error) {
                console.error('camera check failed:', error)
                if (mounted) {
                    setCameraStatus('error')
                }
            }

            try {
                const audioProbeStream = await navigator.mediaDevices.getUserMedia({ audio: true })
                audioProbeStream.getTracks().forEach((track) => track.stop())
                if (mounted) {
                    setMicStatus('ok')
                }
            } catch (error) {
                console.error('microphone check failed:', error)
                if (mounted) {
                    setMicStatus('error')
                }
            }

            if (!mounted && localVideoStream) {
                localVideoStream.getTracks().forEach((track) => track.stop())
            }
        }

        initDevices()
        return () => {
            mounted = false
            if (streamRef.current) {
                streamRef.current.getTracks().forEach((track) => track.stop())
                streamRef.current = null
            }
        }
    }, [])

    useEffect(() => {
        if (cameraStatus !== 'ok') {
            return
        }
        void bindCameraPreview()
    }, [cameraStatus, bindCameraPreview])

    useEffect(() => {
        let cancelled = false
        let retryTimer: ReturnType<typeof setTimeout> | null = null
        const abortController = new AbortController()

        const pollPrewarmStatus = async (remainingRetry = 2) => {
            if (cancelled) {
                return
            }
            try {
                const response = await fetch(`${BACKEND_API_BASE}/api/prewarm?wait=1&wait_timeout=2.5`, {
                    method: 'GET',
                    cache: 'no-store',
                    signal: abortController.signal
                })
                const payload = await response.json().catch(() => ({}))
                const status = String(payload?.data?.status || '').trim().toLowerCase()
                if (cancelled) {
                    return
                }
                if (status === 'completed') {
                    setServiceWarmupStatus('ready')
                    setServiceWarmupText('服务已就绪，开始面试会更快。')
                    return
                }
                if (status === 'partial' || status === 'failed') {
                    setServiceWarmupStatus('error')
                    setServiceWarmupText('部分服务预热失败，开始时可能略有等待。')
                    return
                }
                if (remainingRetry > 0) {
                    retryTimer = setTimeout(() => {
                        void pollPrewarmStatus(remainingRetry - 1)
                    }, 1200)
                } else {
                    setServiceWarmupStatus('warming')
                    setServiceWarmupText('服务仍在后台预热中，可直接开始面试。')
                }
            } catch (error) {
                if (cancelled) {
                    return
                }
                setServiceWarmupStatus('error')
                setServiceWarmupText('无法确认服务预热状态，开始时可能稍有等待。')
            }
        }

        const triggerPrewarm = async () => {
            setServiceWarmupStatus('warming')
            setServiceWarmupText('正在预热服务...')
            try {
                const response = await fetch(`${BACKEND_API_BASE}/api/prewarm?wait=0`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source: 'interview_setup_page' }),
                    cache: 'no-store',
                    signal: abortController.signal
                })
                const payload = await response.json().catch(() => ({}))
                const status = String(payload?.data?.status || '').trim().toLowerCase()
                if (cancelled) {
                    return
                }
                if (status === 'completed') {
                    setServiceWarmupStatus('ready')
                    setServiceWarmupText('服务已就绪，开始面试会更快。')
                    return
                }
                if (status === 'partial' || status === 'failed') {
                    setServiceWarmupStatus('error')
                    setServiceWarmupText('部分服务预热失败，开始时可能略有等待。')
                    return
                }
                void pollPrewarmStatus(2)
            } catch (error) {
                if (cancelled) {
                    return
                }
                setServiceWarmupStatus('error')
                setServiceWarmupText('无法启动后台预热，开始时可能稍有等待。')
            }
        }

        void triggerPrewarm()

        return () => {
            cancelled = true
            abortController.abort()
            if (retryTimer) {
                clearTimeout(retryTimer)
            }
        }
    }, [])

    const isReady = cameraStatus === 'ok'

    const handleStartInterview = () => {
        if (!isReady || isStarting) {
            return
        }
        setIsStarting(true)
        sessionStorage.setItem('interview_config', JSON.stringify({
            round: selectedRound,
            position: selectedPosition,
            difficulty: selectedDifficulty,
            trainingMode: selectedInterviewMode,
        }))
        setTimeout(() => {
            router.push('/interview')
        }, 350)
    }

    return (
        <div className="h-[100dvh] overflow-hidden bg-[#FAF9F6] p-3 sm:p-4 lg:p-5">
            <motion.div
                className="mx-auto grid h-full min-h-0 w-full max-w-7xl gap-4 lg:grid-cols-[1.04fr_1fr] lg:gap-5"
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.55, ease: 'easeOut' }}
            >
                <motion.section className="flex min-h-0 flex-col gap-4" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08, duration: 0.45 }}>
                    <div>
                        <button
                            onClick={() => router.push('/dashboard')}
                            className="motion-press inline-flex items-center gap-1.5 rounded-xl border border-[#E5E5E5] bg-white px-3.5 py-2 text-sm font-medium text-[#555555] shadow-sm transition hover:border-[#d7d7d7] hover:bg-[#F5F5F5] hover:text-[#111111]"
                        >
                            <ArrowLeft size={16} />
                            返回工作台
                        </button>
                        <p className="text-xs font-medium uppercase tracking-[0.16em] text-[#8a8479]">面试前准备</p>
                        <h1 className="mt-1.5 text-[1.7rem] tracking-tight text-[#111111]">开始前检查</h1>
                        <p className="mt-1 text-sm text-[#666666]">确认设备状态并完成本次会话配置。</p>
                        <div className="mt-2 inline-flex items-center gap-2 rounded-full border border-[#E5E5E5] bg-white px-3 py-1.5 text-xs text-[#666666]">
                            <span className={`h-2.5 w-2.5 rounded-full ${serviceWarmupStatus === 'ready' ? 'bg-green-500' : serviceWarmupStatus === 'error' ? 'bg-amber-500' : 'bg-[#111111] animate-pulse'}`} />
                            <span>{serviceWarmupText}</span>
                        </div>
                    </div>

                    <div className="relative h-[clamp(190px,31vh,280px)] overflow-hidden rounded-2xl border border-[#222222] bg-[#111111] shadow-sm">
                        {cameraStatus === 'ok' ? (
                            <video ref={videoRef} autoPlay muted playsInline className="h-full w-full -scale-x-100 object-cover" />
                        ) : (
                            <div className="absolute inset-0 flex items-center justify-center">
                                <div className="flex flex-col items-center gap-3 text-white/60">
                                    {cameraStatus === 'checking' ? <Camera size={32} className="animate-pulse" /> : <AlertCircle size={32} className="text-red-400" />}
                                    <span className="text-sm">{cameraStatus === 'checking' ? '正在连接摄像头...' : '摄像头访问被拒绝'}</span>
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="space-y-2.5">
                        <div className="flex items-center justify-between rounded-xl border border-[#E5E5E5] bg-white p-3">
                            <div className="flex items-center gap-3">
                                <div className={`rounded-full p-2 ${cameraStatus === 'ok' ? 'bg-green-100 text-green-600' : 'bg-[#F5F5F5] text-[#666666]'}`}>
                                    <Camera size={16} />
                                </div>
                                <div>
                                    <div className="text-sm font-medium text-[#111111]">摄像头</div>
                                    <div className="text-xs text-[#666666]">默认摄像头</div>
                                </div>
                            </div>
                            {cameraStatus === 'checking' && <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#111111] border-t-transparent" />}
                            {cameraStatus === 'ok' && <CheckCircle2 size={18} className="text-green-600" />}
                            {cameraStatus === 'error' && <AlertCircle size={18} className="text-red-500" />}
                        </div>

                        <div className="flex items-center justify-between rounded-xl border border-[#E5E5E5] bg-white p-3">
                            <div className="flex items-center gap-3">
                                <div className={`rounded-full p-2 ${micStatus === 'ok' ? 'bg-green-100 text-green-600' : 'bg-[#F5F5F5] text-[#666666]'}`}>
                                    <Mic size={16} />
                                </div>
                                <div>
                                    <div className="text-sm font-medium text-[#111111]">麦克风</div>
                                    <div className="text-xs text-[#666666]">默认输入设备</div>
                                </div>
                            </div>
                            {micStatus === 'checking' && <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#111111] border-t-transparent" />}
                            {micStatus === 'ok' && <CheckCircle2 size={18} className="text-green-600" />}
                            {micStatus === 'error' && <AlertCircle size={18} className="text-red-500" />}
                        </div>
                    </div>
                </motion.section>

                <motion.section className="flex flex-col" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.16, duration: 0.45 }}>
                    <div className="flex h-full min-h-0 flex-col rounded-2xl border border-[#E5E5E5] bg-white p-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)] lg:p-5">
                        <div className="mb-4 flex items-center gap-2">
                            <Settings2 size={17} className="text-[#111111]" />
                            <h2 className="text-base font-medium text-[#111111]">会话配置</h2>
                        </div>

                        <div className="flex-1 min-h-0 space-y-4">
                            <div className="space-y-2.5">
                                <label className="text-sm font-medium text-[#111111]">面试类型</label>
                                <div className="grid grid-cols-2 gap-2.5">
                                    {INTERVIEW_ROUNDS.map((round) => {
                                        const Icon = round.icon
                                        const active = selectedRound === round.id
                                        return (
                                            <button
                                                key={round.id}
                                                onClick={() => setSelectedRound(round.id)}
                                                className={`motion-press rounded-lg border p-2.5 text-left text-[13px] transition-colors ${active ? 'border-[#111111] bg-[#111111] text-white' : 'border-[#E5E5E5] text-[#666666] hover:border-[#111111]'}`}
                                            >
                                                <div className="mb-0.5 flex items-center gap-1.5">
                                                    <Icon size={14} />
                                                    <span>{round.name}</span>
                                                </div>
                                                <p className={`line-clamp-1 text-[11px] leading-4 ${active ? 'text-white/80' : 'text-[#7a7a7a]'}`}>{round.description}</p>
                                            </button>
                                        )
                                    })}
                                </div>
                            </div>

                            <div className="space-y-2.5">
                                <label className="text-sm font-medium text-[#111111]">目标岗位</label>
                                <div className="grid grid-cols-3 gap-2.5">
                                    {POSITIONS.map((position) => (
                                        <button
                                            key={position.id}
                                            onClick={() => setSelectedPosition(position.id)}
                                            className={`motion-press rounded-lg border p-2.5 text-left text-[13px] leading-snug transition-colors ${selectedPosition === position.id ? 'border-[#111111] bg-[#111111] text-white' : 'border-[#E5E5E5] text-[#666666] hover:border-[#111111]'}`}
                                        >
                                            {position.name}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div className="space-y-2.5">
                                <label className="text-sm font-medium text-[#111111]">难度等级</label>
                                <div className="grid grid-cols-3 gap-2.5">
                                    {DIFFICULTY_LEVELS.map((level) => (
                                        <button
                                            key={level.id}
                                            onClick={() => setSelectedDifficulty(level.id)}
                                            className={`motion-press rounded-lg border p-2.5 text-left text-sm transition-colors ${selectedDifficulty === level.id ? 'border-[#111111] bg-[#111111] text-white' : 'border-[#E5E5E5] text-[#666666] hover:border-[#111111]'}`}
                                        >
                                            <p>{level.name}</p>
                                            <p className={`mt-0.5 text-[11px] leading-4 ${selectedDifficulty === level.id ? 'text-white/80' : 'text-[#7a7a7a]'}`}>{level.description}</p>
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div className="space-y-2.5">
                                <label className="text-sm font-medium text-[#111111]">面试方式</label>
                                <div className="grid grid-cols-2 gap-2.5">
                                    <button
                                        onClick={() => setSelectedInterviewMode('realistic_mock')}
                                        className={`motion-press rounded-lg border p-3 text-left transition-colors ${selectedInterviewMode === 'realistic_mock' ? 'border-[#111111] bg-[#111111] text-white' : 'border-[#E5E5E5] text-[#666666] hover:border-[#111111]'}`}
                                    >
                                        <p className="text-sm font-medium">真实面试场景</p>
                                        <p className={`mt-1 text-[11px] leading-5 ${selectedInterviewMode === 'realistic_mock' ? 'text-white/80' : 'text-[#7a7a7a]'}`}>
                                            开场更自然，会邀请你先做简短自我介绍，再切入正式提问。
                                        </p>
                                    </button>
                                    <button
                                        onClick={() => setSelectedInterviewMode('focused_training')}
                                        className={`motion-press rounded-lg border p-3 text-left transition-colors ${selectedInterviewMode === 'focused_training' ? 'border-[#111111] bg-[#111111] text-white' : 'border-[#E5E5E5] text-[#666666] hover:border-[#111111]'}`}
                                    >
                                        <p className="text-sm font-medium">训练模式</p>
                                        <p className={`mt-1 text-[11px] leading-5 ${selectedInterviewMode === 'focused_training' ? 'text-white/80' : 'text-[#7a7a7a]'}`}>
                                            直接进入专项训练，减少铺垫，把时间集中用在高命中率提问和连续追问上。
                                        </p>
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div className="mt-4 border-t border-[#E5E5E5] pt-4">
                            {micStatus !== 'ok' && (
                                <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                                    麦克风不可用，开始后可继续使用文本回答模式。
                                </div>
                            )}
                            <button
                                onClick={handleStartInterview}
                                disabled={!isReady || isStarting}
                                className="motion-press group inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#111111] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#222222] disabled:cursor-not-allowed disabled:bg-[#cacaca]"
                            >
                                <Play size={16} fill="currentColor" className="group-hover:scale-110 transition-transform" />
                                {isReady ? (isStarting ? 'Starting...' : 'Start Interview') : '请先启用摄像头'}
                            </button>
                        </div>
                    </div>
                </motion.section>
            </motion.div>
        </div>
    )
}

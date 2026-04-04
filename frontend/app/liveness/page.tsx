'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import SocketClient from '@/lib/socket'

export default function LivenessPage() {
    const router = useRouter()
    const videoRef = useRef<HTMLVideoElement>(null)
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const [socket, setSocket] = useState<SocketClient | null>(null)

    const [cameraReady, setCameraReady] = useState(false)
    const [socketReady, setSocketReady] = useState(false)
    const [message, setMessage] = useState('正在初始化采集设备...')
    const [blinkDetected, setBlinkDetected] = useState(false)
    const [mouthOpened, setMouthOpened] = useState(false)
    const [verified, setVerified] = useState(false)

    useEffect(() => {
        initCamera()
        initSocket()

        return () => {
            stopCamera()
            socket?.disconnect()
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
                setMessage('设备已就绪，请按提示完成面试前动作校准。')
            }
        } catch (error) {
            console.error('Camera error:', error)
            setMessage('无法访问摄像头，请检查浏览器权限设置。')
        }
    }

    const stopCamera = () => {
        if (videoRef.current && videoRef.current.srcObject) {
            const stream = videoRef.current.srcObject as MediaStream
            stream.getTracks().forEach(track => track.stop())
        }
    }

    const initSocket = async () => {
        const socketClient = SocketClient.getInstance()

        try {
            await socketClient.connect()
            setSocket(socketClient)
            setSocketReady(true)

            socketClient.on('liveness_result', (data: any) => {
                setBlinkDetected(data.blink_detected)
                setMouthOpened(data.mouth_opened)
                setMessage(data.message)

                if (data.verified) {
                    setVerified(true)
                    setTimeout(() => {
                        router.push('/interview')
                    }, 1500)
                }
            })

            socketClient.on('connection_response', () => {
                return
            })
        } catch (error) {
            console.error('Socket connection error:', error)
            setMessage('连接分析服务失败，请确认后端服务已启动。')
        }
    }

    useEffect(() => {
        if (!cameraReady || !socket || !socketReady) return

        const interval = setInterval(() => {
            captureAndSend()
        }, 100)

        return () => clearInterval(interval)
    }, [cameraReady, socket, socketReady])

    const captureAndSend = () => {
        if (!videoRef.current || !canvasRef.current || !socket || !socketReady) return

        const video = videoRef.current
        const canvas = canvasRef.current
        const ctx = canvas.getContext('2d')

        if (!ctx || video.videoWidth === 0) return

        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        ctx.drawImage(video, 0, 0)

        const frame = canvas.toDataURL('image/jpeg', 0.8)
        socket.emit('liveness_check', { frame })
    }

    return (
        <div className="page-shell-compact flex items-center justify-center">
            <div className="w-full max-w-4xl rounded-3xl border border-[#E5E5E5] bg-white p-8 shadow-sm animate-slide-up">
                <h1 className="mb-8 text-center text-3xl text-[#111111]">面试前校准</h1>

                <div className="grid gap-8 md:grid-cols-2">
                    <div className="space-y-4">
                        <div className="relative aspect-[4/3] overflow-hidden rounded-lg bg-black shadow-sm">
                            <video
                                ref={videoRef}
                                autoPlay
                                playsInline
                                muted
                                className="h-full w-full object-cover"
                            />
                            <canvas ref={canvasRef} className="hidden" />

                            {!cameraReady && (
                                <div className="absolute inset-0 flex items-center justify-center bg-black/60">
                                    <div className="text-center text-white">
                                        <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-white border-t-transparent" />
                                        <p className="text-sm">加载摄像头中...</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="space-y-6">
                        <div className="rounded-lg border border-[#E5E5E5] bg-[#FAF9F6] p-6">
                            <h3 className="mb-4 text-lg text-[#111111]">校准状态</h3>

                            <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <span className="text-[#666666]">眨眼动作</span>
                                    <span className={`font-medium ${blinkDetected ? 'text-green-600' : 'text-[#999999]'}`}>
                                        {blinkDetected ? '✓ 已检测' : '○ 等待中'}
                                    </span>
                                </div>

                                <div className="flex items-center justify-between">
                                    <span className="text-[#666666]">开合动作</span>
                                    <span className={`font-medium ${mouthOpened ? 'text-green-600' : 'text-[#999999]'}`}>
                                        {mouthOpened ? '✓ 已检测' : '○ 等待中'}
                                    </span>
                                </div>
                            </div>
                        </div>

                        <div className={`rounded-lg border p-4 ${verified ? 'border-green-300 bg-green-50' : 'border-[#E5E5E5] bg-[#FAF9F6]'}`}>
                            <p className={`text-center text-sm font-medium ${verified ? 'text-green-700' : 'text-[#666666]'}`}>
                                {message}
                            </p>
                        </div>

                        {verified && (
                            <div className="text-center animate-fade-in">
                                <div className="inline-block animate-bounce">
                                    <svg className="mx-auto h-14 w-14 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                    </svg>
                                </div>
                                <p className="mt-2 text-sm font-medium text-green-700">校准完成，正在进入 AI 模拟面试...</p>
                            </div>
                        )}

                        <div className="rounded-lg border border-[#E5E5E5] bg-[#FAF9F6] p-4 text-sm text-[#666666]">
                            <p className="mb-2 font-medium text-[#111111]">引导说明：</p>
                            <ol className="list-inside list-decimal space-y-1">
                                <li>正视摄像头</li>
                                <li>自然眨眼</li>
                                <li>张大嘴巴</li>
                                <li>等待验证完成</li>
                            </ol>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

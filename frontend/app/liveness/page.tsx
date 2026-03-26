'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import SocketClient from '@/lib/socket'
import { Home, FileText } from 'lucide-react'

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
            console.log('Socket connected successfully')

            socketClient.on('liveness_result', (data: any) => {
                console.log('Received liveness_result:', data)
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

            socketClient.on('connection_response', (data: any) => {
                console.log('Server connection response:', data)
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
        }, 100) // 10 fps

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
        <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-100 dark:from-gray-900 dark:to-blue-950 flex items-center justify-center p-4 transition-colors">
            {/* Navigation Header */}
            <div className="fixed top-4 left-4 z-50 flex gap-2">
                <button
                    onClick={() => router.push('/')}
                    className="flex items-center gap-2 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 px-4 py-2 rounded-lg shadow-lg transition-all border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-200"
                >
                    <Home className="w-5 h-5" />
                    <span className="text-sm font-medium">首页</span>
                </button>
                <button
                    onClick={() => router.push('/report')}
                    className="flex items-center gap-2 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 px-4 py-2 rounded-lg shadow-lg transition-all border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-200"
                >
                    <FileText className="w-5 h-5" />
                    <span className="text-sm font-medium">报告</span>
                </button>
            </div>

            <div className="max-w-4xl w-full bg-white dark:bg-gray-800 rounded-lg shadow-xl p-8 animate-slide-up">
                <h1 className="text-3xl font-bold text-center mb-8 text-gray-800 dark:text-gray-100">
                    面试前校准
                </h1>

                <div className="grid md:grid-cols-2 gap-8">
                    {/* Video Preview */}
                    <div className="space-y-4">
                        <div className="relative bg-black rounded-lg overflow-hidden shadow-xl" style={{ aspectRatio: '4/3' }}>
                            <video
                                ref={videoRef}
                                autoPlay
                                playsInline
                                muted
                                className="w-full h-full object-cover"
                            />
                            <canvas ref={canvasRef} className="hidden" />

                            {!cameraReady && (
                                <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50">
                                    <div className="text-white text-center">
                                        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
                                        <p>加载摄像头中...</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Status Panel */}
                    <div className="space-y-6">
                        <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded-lg p-6">
                            <h3 className="font-semibold text-lg mb-4 text-gray-800 dark:text-gray-100">校准状态</h3>

                            <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <span className="text-gray-700 dark:text-gray-300">眨眼动作</span>
                                    <span className={`font-semibold ${blinkDetected ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'}`}>
                                        {blinkDetected ? '✓ 已检测' : '○ 等待中'}
                                    </span>
                                </div>

                                <div className="flex items-center justify-between">
                                    <span className="text-gray-700 dark:text-gray-300">开合动作</span>
                                    <span className={`font-semibold ${mouthOpened ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'}`}>
                                        {mouthOpened ? '✓ 已检测' : '○ 等待中'}
                                    </span>
                                </div>
                            </div>
                        </div>

                        <div className={`p-4 rounded-lg ${verified ? 'bg-green-100 dark:bg-green-900/30 border border-green-300 dark:border-green-800' : 'bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600'}`}>
                            <p className={`text-center font-medium ${verified ? 'text-green-800 dark:text-green-200' : 'text-gray-700 dark:text-gray-300'}`}>
                                {message}
                            </p>
                        </div>

                        {verified && (
                            <div className="text-center animate-fade-in">
                                <div className="inline-block animate-bounce">
                                    <svg className="w-16 h-16 text-green-500 dark:text-green-400 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                    </svg>
                                </div>
                                <p className="text-green-600 dark:text-green-400 font-semibold mt-2">校准完成，正在进入 AI 模拟面试...</p>
                            </div>
                        )}

                        <div className="text-sm text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                            <p className="font-semibold mb-2">引导说明：</p>
                            <ol className="list-decimal list-inside space-y-1">
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

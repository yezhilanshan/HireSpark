'use client'

import { type RefObject, useEffect, useRef, useState } from 'react'

const TARGET_FPS = 30
const FRAME_INTERVAL = 1000 / TARGET_FPS
const INPUT_BUFFER_SIZE = 450
const SQI_THRESHOLD = 0.38
const FACE_TIMEOUT_MS = 500
const MODEL_BASE = '/facephys/models'
const WORKER_BASE = '/facephys'
const MEDIAPIPE_WASM_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/wasm'
const DELEGATE_INFO_SNIPPETS = [
    'Created TensorFlow Lite XNNPACK delegate for CPU',
    'INFO: Created TensorFlow Lite XNNPACK delegate for CPU'
]

type RppgStatus = 'idle' | 'loading' | 'tracking' | 'unstable' | 'no_face' | 'error'

export type RppgMetrics = {
    hr: number | null
    sqi: number | null
    isReliable: boolean
    hasFace: boolean
    latencyMs: number | null
    fps: number | null
    status: RppgStatus
    error?: string
}

type WorkerMessage = {
    type: string
    payload?: any
    msg?: string
}

type FacePhysAssets = {
    model: Uint8Array
    proj: Uint8Array
    sqi: Uint8Array
    psd: Uint8Array
    stateJson: Record<string, unknown>
}

type SessionRefs = {
    inferenceWorker: Worker | null
    psdWorker: Worker | null
    rafId: number | null
    buffer: Float32Array
    bufferPtr: number
    bufferFull: boolean
    frameCount: number
    lastFrameTime: number
    lastFpsAt: number
    fpsValue: number | null
    currentCaptureTime: number
    virtualTime: number
    dval: number
    lastFaceDetectTime: number
    latencyMs: number | null
    detectorErrorCount: number
}

const shouldSuppressDelegateLog = (args: unknown[]): boolean => {
    if (!args || args.length === 0) return false
    const text = args
        .map((item) => String(item ?? ''))
        .join(' ')
        .trim()
    if (!text) return false
    return DELEGATE_INFO_SNIPPETS.some((snippet) => text.includes(snippet))
}

const withFilteredDelegateLogs = <T,>(run: () => T): T => {
    const originalError = console.error
    const originalWarn = console.warn
    const originalInfo = console.info
    const originalLog = console.log
    try {
        console.error = (...args: unknown[]) => {
            if (shouldSuppressDelegateLog(args)) return
            originalError(...args)
        }
        console.warn = (...args: unknown[]) => {
            if (shouldSuppressDelegateLog(args)) return
            originalWarn(...args)
        }
        console.info = (...args: unknown[]) => {
            if (shouldSuppressDelegateLog(args)) return
            originalInfo(...args)
        }
        console.log = (...args: unknown[]) => {
            if (shouldSuppressDelegateLog(args)) return
            originalLog(...args)
        }
        return run()
    } finally {
        console.error = originalError
        console.warn = originalWarn
        console.info = originalInfo
        console.log = originalLog
    }
}

class KalmanFilter1D {
    private x: number

    private p: number

    private readonly q: number

    private readonly r: number

    constructor(initialValue: number, processNoise = 1e-2, measurementNoise = 5e-1) {
        this.x = initialValue
        this.p = 1.0
        this.q = processNoise
        this.r = measurementNoise
    }

    update(measurement: number) {
        const predicted = this.p + this.q
        const k = predicted / (predicted + this.r)
        this.x = this.x + k * (measurement - this.x)
        this.p = (1 - k) * predicted
        return this.x
    }
}

const createEmptyMetrics = (): RppgMetrics => ({
    hr: null,
    sqi: null,
    isReliable: false,
    hasFace: false,
    latencyMs: null,
    fps: null,
    status: 'idle'
})

let assetsPromise: Promise<FacePhysAssets> | null = null

async function loadFacePhysAssets(): Promise<FacePhysAssets> {
    if (!assetsPromise) {
        assetsPromise = (async () => {
            const [modelRes, projRes, sqiRes, psdRes, stateRes] = await Promise.all([
                fetch(`${MODEL_BASE}/model.tflite`),
                fetch(`${MODEL_BASE}/proj.tflite`),
                fetch(`${MODEL_BASE}/sqi_model.tflite`),
                fetch(`${MODEL_BASE}/psd_model.tflite`),
                fetch(`${MODEL_BASE}/state.gz`)
            ])

            if (!modelRes.ok || !projRes.ok || !sqiRes.ok || !psdRes.ok || !stateRes.ok) {
                throw new Error('FacePhys model assets failed to load')
            }

            if (typeof DecompressionStream === 'undefined') {
                throw new Error('Current browser does not support DecompressionStream')
            }

            const ds = new DecompressionStream('gzip')
            const stateStream = stateRes.body?.pipeThrough(ds)
            if (!stateStream) {
                throw new Error('FacePhys state stream is unavailable')
            }

            const stateJson = await new Response(stateStream).json() as Record<string, unknown>

            return {
                model: new Uint8Array(await modelRes.arrayBuffer()),
                proj: new Uint8Array(await projRes.arrayBuffer()),
                sqi: new Uint8Array(await sqiRes.arrayBuffer()),
                psd: new Uint8Array(await psdRes.arrayBuffer()),
                stateJson
            }
        })()
    }

    return assetsPromise
}

async function loadVisionTasks() {
    const visionModule = await import(
        /* webpackIgnore: true */
        'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/+esm'
    ) as any
    const vision = await visionModule.FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_URL)
    return { FaceDetector: visionModule.FaceDetector, vision }
}

function cloneBuffer(bytes: Uint8Array) {
    return bytes.slice().buffer
}

function createSessionRefs(): SessionRefs {
    return {
        inferenceWorker: null,
        psdWorker: null,
        rafId: null,
        buffer: new Float32Array(INPUT_BUFFER_SIZE),
        bufferPtr: 0,
        bufferFull: false,
        frameCount: 0,
        lastFrameTime: 0,
        lastFpsAt: 0,
        fpsValue: null,
        currentCaptureTime: 0,
        virtualTime: 0,
        dval: 1 / 30,
        lastFaceDetectTime: 0,
        latencyMs: null,
        detectorErrorCount: 0
    }
}

function orderBuffer(buffer: Float32Array, bufferPtr: number, bufferFull: boolean) {
    if (!bufferFull) {
        const ordered = new Float32Array(INPUT_BUFFER_SIZE)
        ordered.set(buffer.slice(0, bufferPtr), INPUT_BUFFER_SIZE - bufferPtr)
        return ordered
    }

    const ordered = new Float32Array(INPUT_BUFFER_SIZE)
    ordered.set(buffer.subarray(bufferPtr), 0)
    ordered.set(buffer.subarray(0, bufferPtr), INPUT_BUFFER_SIZE - bufferPtr)
    return ordered
}

export function useFacePhysRppg(videoRef: RefObject<HTMLVideoElement>, enabled: boolean): RppgMetrics {
    const [metrics, setMetrics] = useState<RppgMetrics>(createEmptyMetrics)

    const faceDetectorRef = useRef<any>(null)
    const faceDetectorPromiseRef = useRef<Promise<any> | null>(null)
    const cropCanvasRef = useRef<HTMLCanvasElement | null>(null)
    const cropCtxRef = useRef<CanvasRenderingContext2D | null>(null)
    const sessionRef = useRef<SessionRefs>(createSessionRefs())
    const sessionIdRef = useRef(0)
    const metricsRef = useRef<RppgMetrics>(createEmptyMetrics())
    const lastUiUpdateRef = useRef(0)
    const boxFiltersRef = useRef<{
        x: KalmanFilter1D
        y: KalmanFilter1D
        w: KalmanFilter1D
        h: KalmanFilter1D
    } | null>(null)

    const flushMetrics = (patch: Partial<RppgMetrics>, force = false) => {
        const next = { ...metricsRef.current, ...patch }
        metricsRef.current = next
        const now = performance.now()
        if (!force && now - lastUiUpdateRef.current < 250) {
            return
        }
        lastUiUpdateRef.current = now
        setMetrics(next)
    }

    const resetSessionState = () => {
        sessionRef.current = createSessionRefs()
        boxFiltersRef.current = null
    }

    const stopSession = (nextStatus: RppgStatus = enabled ? 'loading' : 'idle') => {
        const session = sessionRef.current
        if (session.rafId !== null) {
            cancelAnimationFrame(session.rafId)
            session.rafId = null
        }
        session.inferenceWorker?.terminate()
        session.psdWorker?.terminate()
        resetSessionState()
        flushMetrics({
            hr: null,
            sqi: null,
            isReliable: false,
            hasFace: false,
            latencyMs: null,
            fps: null,
            status: nextStatus,
            error: undefined
        }, true)
    }

    const ensureCropCanvas = () => {
        if (!cropCanvasRef.current) {
            const canvas = document.createElement('canvas')
            canvas.width = 36
            canvas.height = 36
            cropCanvasRef.current = canvas
            cropCtxRef.current = canvas.getContext('2d', { willReadFrequently: true })
        }

        if (!cropCtxRef.current) {
            throw new Error('Unable to create crop canvas context')
        }

        return cropCtxRef.current
    }

    const ensureFaceDetector = async () => {
        if (faceDetectorRef.current) {
            return faceDetectorRef.current
        }

        if (!faceDetectorPromiseRef.current) {
            faceDetectorPromiseRef.current = (async () => {
                const { FaceDetector, vision } = await loadVisionTasks()
                try {
                    return await FaceDetector.createFromOptions(vision, {
                        baseOptions: {
                            modelAssetPath: `${MODEL_BASE}/blaze_face_short_range.tflite`,
                            delegate: 'GPU'
                        },
                        runningMode: 'VIDEO'
                    })
                } catch {
                    return FaceDetector.createFromOptions(vision, {
                        baseOptions: {
                            modelAssetPath: `${MODEL_BASE}/blaze_face_short_range.tflite`,
                            delegate: 'CPU'
                        },
                        runningMode: 'VIDEO'
                    })
                }
            })()
        }

        faceDetectorRef.current = await faceDetectorPromiseRef.current
        return faceDetectorRef.current
    }

    const startLoop = (sessionId: number) => {
        const session = sessionRef.current

        const tick = () => {
            if (sessionIdRef.current !== sessionId) {
                return
            }

            const video = videoRef.current
            if (!video || video.readyState < 2 || video.videoWidth === 0 || video.videoHeight === 0) {
                session.rafId = requestAnimationFrame(tick)
                return
            }

            const now = performance.now()
            if (session.lastFrameTime === 0) {
                session.lastFrameTime = now
                session.lastFpsAt = now
            }

            const elapsed = now - session.lastFrameTime
            if (elapsed < FRAME_INTERVAL) {
                session.rafId = requestAnimationFrame(tick)
                return
            }

            session.lastFrameTime = now - (elapsed % FRAME_INTERVAL)
            session.frameCount += 1

            const elapsedFps = now - session.lastFpsAt
            if (elapsedFps >= 1000) {
                session.fpsValue = Number(((session.frameCount * 1000) / elapsedFps).toFixed(1))
                session.frameCount = 0
                session.lastFpsAt = now
                flushMetrics({ fps: session.fpsValue })
            }

            try {
                processFrame()
            } catch (error) {
                const message = error instanceof Error ? error.message : 'rPPG frame processing failed'
                sessionIdRef.current += 1
                stopSession('error')
                flushMetrics({
                    status: 'error',
                    error: message
                }, true)
                return
            }

            session.rafId = requestAnimationFrame(tick)
        }

        session.rafId = requestAnimationFrame(tick)
    }

    const handleInferenceResult = (sessionId: number, payload: any) => {
        if (sessionIdRef.current !== sessionId) {
            return
        }

        const session = sessionRef.current
        session.latencyMs = typeof payload?.time === 'number' ? payload.time : null

        const value = typeof payload?.value === 'number' ? payload.value : 0
        session.buffer[session.bufferPtr] = value
        session.bufferPtr = (session.bufferPtr + 1) % INPUT_BUFFER_SIZE
        if (session.bufferPtr === 0) {
            session.bufferFull = true
        }

        const orderedData = orderBuffer(session.buffer, session.bufferPtr, session.bufferFull)
        session.psdWorker?.postMessage({
            type: 'run',
            payload: { inputData: orderedData }
        })

        flushMetrics({
            latencyMs: session.latencyMs
        })
    }

    const handlePsdResult = (sessionId: number, payload: any) => {
        if (sessionIdRef.current !== sessionId) {
            return
        }

        const session = sessionRef.current
        const sqi = typeof payload?.sqi === 'number' ? payload.sqi : null
        const hasFace = performance.now() - session.lastFaceDetectTime < FACE_TIMEOUT_MS
        const reliable = Boolean(hasFace && sqi !== null && sqi > SQI_THRESHOLD && session.dval > 0)
        const rawHr = typeof payload?.hr === 'number' ? payload.hr : null
        const hr = reliable && rawHr !== null
            ? Number((rawHr / 30.0 / session.dval).toFixed(1))
            : null

        flushMetrics({
            hr,
            sqi,
            isReliable: reliable,
            hasFace,
            latencyMs: session.latencyMs,
            fps: session.fpsValue,
            status: hasFace ? (reliable ? 'tracking' : 'unstable') : 'no_face',
            error: undefined
        })
    }

    const handleWorkerError = (sessionId: number, msg?: string) => {
        if (sessionIdRef.current !== sessionId) {
            return
        }

        sessionIdRef.current += 1
        stopSession('error')
        flushMetrics({
            status: 'error',
            error: msg || 'FacePhys worker error'
        }, true)
    }

    const processFrame = () => {
        const video = videoRef.current
        const faceDetector = faceDetectorRef.current
        if (!video || !faceDetector) {
            return
        }

        const session = sessionRef.current
        const cropCtx = ensureCropCanvas()
        const captureTime = Date.now()

        if (session.currentCaptureTime > 0) {
            session.dval = session.dval * 0.997 + 0.003 * ((captureTime - session.currentCaptureTime) / 1000)
            session.virtualTime += session.dval * 1000
            session.virtualTime = session.virtualTime * 0.997 + 0.003 * captureTime
        } else {
            session.currentCaptureTime = captureTime
            session.virtualTime = captureTime
        }

        let detections: any
        try {
            detections = withFilteredDelegateLogs(() => faceDetector.detectForVideo(video, performance.now()))
            session.detectorErrorCount = 0
        } catch (error) {
            session.detectorErrorCount += 1
            if (session.detectorErrorCount <= 3) {
                const message = error instanceof Error ? error.message : String(error)
                console.warn('[FacePhysRppg] detectForVideo 单帧失败，已跳过：', message)
            }
            if (session.detectorErrorCount >= 15) {
                throw error
            }
            session.currentCaptureTime = captureTime
            return
        }
        const detection = detections?.detections?.[0]

        if (!detection?.boundingBox) {
            session.buffer.fill(0)
            session.bufferPtr = 0
            session.bufferFull = false
            session.currentCaptureTime = captureTime
            flushMetrics({
                hr: null,
                sqi: null,
                isReliable: false,
                hasFace: false,
                status: 'no_face'
            }, true)
            return
        }

        session.lastFaceDetectTime = performance.now()

        let { originX, originY, width, height } = detection.boundingBox
        if (!boxFiltersRef.current) {
            boxFiltersRef.current = {
                x: new KalmanFilter1D(originX),
                y: new KalmanFilter1D(originY),
                w: new KalmanFilter1D(width),
                h: new KalmanFilter1D(height)
            }
        } else {
            originX = boxFiltersRef.current.x.update(originX)
            originY = boxFiltersRef.current.y.update(originY)
            width = boxFiltersRef.current.w.update(width)
            height = boxFiltersRef.current.h.update(height)
        }

        height *= 1.2
        originY -= height * 0.2

        const sx = Math.max(0, originX)
        const sy = Math.max(0, originY)
        const sw = Math.min(width, video.videoWidth - sx)
        const sh = Math.min(height, video.videoHeight - sy)

        if (sw <= 0 || sh <= 0) {
            session.currentCaptureTime = captureTime
            return
        }

        cropCtx.drawImage(video, sx, sy, sw, sh, 0, 0, 36, 36)
        const imgData = cropCtx.getImageData(0, 0, 36, 36)
        const inputFloat32 = new Float32Array(36 * 36 * 3)
        for (let i = 0; i < imgData.data.length; i += 4) {
            const idx = i / 4
            inputFloat32[idx * 3] = imgData.data[i] / 255.0
            inputFloat32[idx * 3 + 1] = imgData.data[i + 1] / 255.0
            inputFloat32[idx * 3 + 2] = imgData.data[i + 2] / 255.0
        }

        session.inferenceWorker?.postMessage({
            type: 'run',
            payload: {
                imgData: inputFloat32,
                dtVal: session.dval,
                timestamp: session.virtualTime
            }
        }, [inputFloat32.buffer])

        session.currentCaptureTime = captureTime
    }

    useEffect(() => {
        if (!enabled) {
            sessionIdRef.current += 1
            stopSession('idle')
            return
        }

        let cancelled = false
        let isStarting = false
        const pendingSessionId = sessionIdRef.current + 1

        const startSession = async () => {
            const video = videoRef.current
            if (!video || video.readyState < 2 || video.videoWidth === 0 || video.videoHeight === 0) {
                return false
            }

            if (cancelled || sessionIdRef.current >= pendingSessionId) {
                return true
            }

            if (isStarting) {
                return false
            }

            isStarting = true
            try {
                flushMetrics({
                    ...createEmptyMetrics(),
                    status: 'loading'
                }, true)

                const [assets] = await Promise.all([
                    loadFacePhysAssets(),
                    ensureFaceDetector()
                ])

                if (cancelled) {
                    return true
                }

                stopSession('loading')
                sessionIdRef.current = pendingSessionId

                const session = sessionRef.current
                session.inferenceWorker = new Worker(`${WORKER_BASE}/inference_worker.js`)
                session.psdWorker = new Worker(`${WORKER_BASE}/psd_worker.js`)

                const isLowPower = window.innerWidth <= 800
                session.inferenceWorker.postMessage({ type: 'setMode', payload: { isLowPower } })
                session.psdWorker.postMessage({ type: 'setMode', payload: { isLowPower } })

                const inferenceReady = new Promise<void>((resolve, reject) => {
                    session.inferenceWorker!.onmessage = (event: MessageEvent<WorkerMessage>) => {
                        const data = event.data
                        if (data.type === 'initDone') {
                            resolve()
                            return
                        }
                        if (data.type === 'error') {
                            reject(new Error(data.msg || 'Inference worker failed to initialize'))
                            return
                        }
                        if (data.type === 'result') {
                            handleInferenceResult(pendingSessionId, data.payload)
                        }
                    }
                    session.inferenceWorker!.onerror = () => {
                        reject(new Error('Inference worker crashed during initialization'))
                    }
                })

                const psdReady = new Promise<void>((resolve, reject) => {
                    session.psdWorker!.onmessage = (event: MessageEvent<WorkerMessage>) => {
                        const data = event.data
                        if (data.type === 'initDone') {
                            resolve()
                            return
                        }
                        if (data.type === 'error') {
                            reject(new Error(data.msg || 'PSD worker failed to initialize'))
                            return
                        }
                        if (data.type === 'result') {
                            handlePsdResult(pendingSessionId, data.payload)
                        }
                    }
                    session.psdWorker!.onerror = () => {
                        reject(new Error('PSD worker crashed during initialization'))
                    }
                })

                const modelBuffer = cloneBuffer(assets.model)
                const projBuffer = cloneBuffer(assets.proj)
                const sqiBuffer = cloneBuffer(assets.sqi)
                const psdBuffer = cloneBuffer(assets.psd)

                session.inferenceWorker.postMessage({
                    type: 'init',
                    payload: {
                        modelBuffer,
                        stateJson: assets.stateJson,
                        projBuffer
                    }
                }, [modelBuffer, projBuffer])

                session.psdWorker.postMessage({
                    type: 'init',
                    payload: {
                        sqiBuffer,
                        psdBuffer
                    }
                }, [sqiBuffer, psdBuffer])

                await Promise.all([inferenceReady, psdReady])

                if (cancelled || sessionIdRef.current !== pendingSessionId) {
                    return true
                }

                session.inferenceWorker.onmessage = (event: MessageEvent<WorkerMessage>) => {
                    const data = event.data
                    if (data.type === 'result') {
                        handleInferenceResult(pendingSessionId, data.payload)
                    } else if (data.type === 'error') {
                        handleWorkerError(pendingSessionId, data.msg)
                    }
                }

                session.psdWorker.onmessage = (event: MessageEvent<WorkerMessage>) => {
                    const data = event.data
                    if (data.type === 'result') {
                        handlePsdResult(pendingSessionId, data.payload)
                    } else if (data.type === 'error') {
                        handleWorkerError(pendingSessionId, data.msg)
                    }
                }

                const handleResize = () => {
                    const lowPower = window.innerWidth <= 800
                    session.inferenceWorker?.postMessage({ type: 'setMode', payload: { isLowPower: lowPower } })
                    session.psdWorker?.postMessage({ type: 'setMode', payload: { isLowPower: lowPower } })
                }

                window.addEventListener('resize', handleResize)
                startLoop(pendingSessionId)

                return () => {
                    window.removeEventListener('resize', handleResize)
                }
            } catch (error) {
                const message = error instanceof Error ? error.message : 'Failed to initialize FacePhys'
                sessionIdRef.current += 1
                stopSession('error')
                flushMetrics({
                    status: 'error',
                    error: message
                }, true)
                return true
            } finally {
                isStarting = false
            }
        }

        let cleanupResize: (() => void) | undefined
        const startInterval = window.setInterval(async () => {
            const result = await startSession()
            if (typeof result === 'function') {
                cleanupResize = result
                clearInterval(startInterval)
            } else if (result === true) {
                clearInterval(startInterval)
            }
        }, 250)

        void startSession().then(result => {
            if (typeof result === 'function') {
                cleanupResize = result
                clearInterval(startInterval)
            } else if (result === true) {
                clearInterval(startInterval)
            }
        })

        return () => {
            cancelled = true
            clearInterval(startInterval)
            cleanupResize?.()
            sessionIdRef.current += 1
            stopSession('idle')
        }
    }, [enabled, videoRef])

    useEffect(() => {
        return () => {
            sessionIdRef.current += 1
            stopSession('idle')
            faceDetectorRef.current?.close?.()
            faceDetectorRef.current = null
            faceDetectorPromiseRef.current = null
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    return metrics
}

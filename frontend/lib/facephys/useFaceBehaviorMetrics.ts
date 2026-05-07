'use client'

import { useEffect, useRef, useState, type RefObject } from 'react'

const MEDIAPIPE_WASM_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/wasm'
const FACE_LANDMARKER_MODEL_URL = '/face_landmarker.task'

const ANALYZE_FPS = 8
const ANALYZE_FRAME_INTERVAL_MS = Math.round(1000 / ANALYZE_FPS)
const UI_UPDATE_INTERVAL_MS = 240
const BLINK_THRESHOLD = 0.55
const GAZE_DRIFT_THRESHOLD = 0.18

const MOUTH_UPPER_LIP_INDEX = 13
const MOUTH_LOWER_LIP_INDEX = 14
const MOUTH_LEFT_CORNER_INDEX = 61
const MOUTH_RIGHT_CORNER_INDEX = 291

const LEFT_EYE_OUTER_INDEX = 33
const LEFT_EYE_INNER_INDEX = 133
const RIGHT_EYE_OUTER_INDEX = 263
const RIGHT_EYE_INNER_INDEX = 362

const LEFT_IRIS_INDICES = [468, 469, 470, 471, 472]
const RIGHT_IRIS_INDICES = [473, 474, 475, 476, 477]
const MICRO_MOVEMENT_INDICES = [1, 33, 61, 199, 263, 291]
const FACE_DISTANCE_INDICES = [1, 33, 263, 199]

const KEY_BLENDSHAPE_NAMES = [
    'eyeBlinkLeft',
    'eyeBlinkRight',
    'browInnerUp',
    'mouthSmileLeft',
    'mouthSmileRight',
    'jawOpen'
] as const

type FaceMetricStatus = 'idle' | 'loading' | 'tracking' | 'no_face' | 'error'

type Point3D = {
    x: number
    y: number
    z: number
}

type EulerAngles = {
    pitch: number
    yaw: number
    roll: number
}

type GazeOffset = {
    x: number
    y: number
    magnitude: number
}

export type FaceBehaviorMetrics = {
    status: FaceMetricStatus
    hasFace: boolean
    faceCount: number
    sampleCount: number
    landmarks3d: {
        landmark_count: number
        mouth_open_ratio: number | null
        micro_movement_variance: number | null
        face_distance_z: number | null
    }
    blendshapes: {
        available_count: number
        key_current: Record<string, number>
        averages: Record<string, number>
        blink_rate_per_min: number | null
        brow_inner_up_avg: number | null
        smile_avg: number | null
        jaw_open_avg: number | null
    }
    headPose: EulerAngles | null
    irisTracking: {
        gaze_offset_x: number | null
        gaze_offset_y: number | null
        gaze_offset_magnitude: number | null
        gaze_focus_score: number | null
        drift_count: number
    }
    error?: string
}

type VisionModule = {
    FilesetResolver: {
        forVisionTasks: (wasmPath: string) => Promise<unknown>
    }
    FaceLandmarker: {
        createFromOptions: (vision: unknown, options: Record<string, unknown>) => Promise<FaceLandmarker>
    }
}

type FaceBlendshapeCategory = {
    categoryName?: string
    score?: number
}

type FaceLandmarkerResult = {
    faceLandmarks?: Array<Array<Point3D>>
    faceBlendshapes?: Array<{ categories?: FaceBlendshapeCategory[] }>
    facialTransformationMatrixes?: Array<{ data?: number[] }>
}

type FaceLandmarker = {
    detectForVideo: (video: HTMLVideoElement, timestamp: number) => FaceLandmarkerResult
    detect?: (input: HTMLVideoElement | HTMLCanvasElement | ImageData) => FaceLandmarkerResult
    close?: () => void
}

const DELEGATE_INFO_SNIPPETS = [
    'Created TensorFlow Lite XNNPACK delegate for CPU',
    'INFO: Created TensorFlow Lite XNNPACK delegate for CPU'
]

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

const EMPTY_METRICS: FaceBehaviorMetrics = {
    status: 'idle',
    hasFace: false,
    faceCount: 0,
    sampleCount: 0,
    landmarks3d: {
        landmark_count: 0,
        mouth_open_ratio: null,
        micro_movement_variance: null,
        face_distance_z: null,
    },
    blendshapes: {
        available_count: 0,
        key_current: {},
        averages: {},
        blink_rate_per_min: null,
        brow_inner_up_avg: null,
        smile_avg: null,
        jaw_open_avg: null,
    },
    headPose: null,
    irisTracking: {
        gaze_offset_x: null,
        gaze_offset_y: null,
        gaze_offset_magnitude: null,
        gaze_focus_score: null,
        drift_count: 0,
    },
    error: undefined,
}

const roundNum = (value: number | null | undefined, digits = 4): number | null => {
    if (value == null || !Number.isFinite(value)) return null
    const factor = 10 ** digits
    return Math.round(value * factor) / factor
}

const clamp = (value: number, min: number, max: number): number => {
    if (!Number.isFinite(value)) return min
    return Math.min(max, Math.max(min, value))
}

const distance2d = (a: Point3D | null | undefined, b: Point3D | null | undefined): number => {
    if (!a || !b) return 0
    const dx = Number(a.x || 0) - Number(b.x || 0)
    const dy = Number(a.y || 0) - Number(b.y || 0)
    return Math.hypot(dx, dy)
}

const mean = (values: number[]): number | null => {
    if (!values.length) return null
    return values.reduce((acc, cur) => acc + cur, 0) / values.length
}

const variance = (values: number[]): number | null => {
    if (!values.length) return null
    const avg = mean(values)
    if (avg == null) return null
    const value = values.reduce((acc, cur) => acc + ((cur - avg) ** 2), 0) / values.length
    return value
}

const avgPoint = (landmarks: Point3D[], indices: number[]): Point3D | null => {
    const pts = indices
        .map((index) => landmarks[index])
        .filter((pt): pt is Point3D => Boolean(pt && Number.isFinite(pt.x) && Number.isFinite(pt.y) && Number.isFinite(pt.z)))
    if (!pts.length) return null
    const x = pts.reduce((acc, pt) => acc + pt.x, 0) / pts.length
    const y = pts.reduce((acc, pt) => acc + pt.y, 0) / pts.length
    const z = pts.reduce((acc, pt) => acc + pt.z, 0) / pts.length
    return { x, y, z }
}

const extractBlendshapeMap = (categories: FaceBlendshapeCategory[] | undefined): Record<string, number> => {
    const result: Record<string, number> = {}
    for (const item of categories || []) {
        const name = String(item?.categoryName || '').trim()
        if (!name) continue
        const score = Number(item?.score)
        if (!Number.isFinite(score)) continue
        result[name] = clamp(score, 0, 1)
    }
    return result
}

const extractEulerAngles = (matrixData: number[] | undefined): EulerAngles | null => {
    if (!Array.isArray(matrixData) || matrixData.length < 16) return null
    const r00 = Number(matrixData[0] || 0)
    const r10 = Number(matrixData[4] || 0)
    const r20 = Number(matrixData[8] || 0)
    const r21 = Number(matrixData[9] || 0)
    const r22 = Number(matrixData[10] || 0)
    const r01 = Number(matrixData[1] || 0)
    const r11 = Number(matrixData[5] || 0)

    const sy = Math.sqrt((r00 * r00) + (r10 * r10))
    const singular = sy < 1e-6

    let pitch = 0
    let yaw = 0
    let roll = 0

    if (!singular) {
        pitch = Math.atan2(r21, r22)
        yaw = Math.atan2(-r20, sy)
        roll = Math.atan2(r10, r00)
    } else {
        pitch = Math.atan2(-Number(matrixData[6] || 0), Number(matrixData[5] || 0))
        yaw = Math.atan2(-r20, sy)
        roll = Math.atan2(-r01, r11)
    }

    return {
        pitch: roundNum((pitch * 180) / Math.PI, 2) || 0,
        yaw: roundNum((yaw * 180) / Math.PI, 2) || 0,
        roll: roundNum((roll * 180) / Math.PI, 2) || 0,
    }
}

export function useFaceBehaviorMetrics(videoRef: RefObject<HTMLVideoElement>, enabled: boolean): FaceBehaviorMetrics {
    const [metrics, setMetrics] = useState<FaceBehaviorMetrics>(EMPTY_METRICS)

    const landmarkerRef = useRef<FaceLandmarker | null>(null)
    const landmarkerPromiseRef = useRef<Promise<FaceLandmarker> | null>(null)
    const rafIdRef = useRef<number | null>(null)
    const sessionIdRef = useRef(0)
    const lastAnalyzeAtRef = useRef(0)
    const lastUiUpdateAtRef = useRef(0)
    const startedAtRef = useRef(0)
    const sampleCountRef = useRef(0)
    const blinkCountRef = useRef(0)
    const lastBlinkStateRef = useRef(false)
    const lastDriftFlagRef = useRef(false)
    const driftCountRef = useRef(0)
    const movementWindowRef = useRef<number[]>([])
    const previousMicroPointsRef = useRef<Point3D[] | null>(null)
    const blendshapeSumsRef = useRef<Record<string, number>>({})
    const blendshapeSamplesRef = useRef(0)
    const lastVideoTimeRef = useRef(-1)
    const lastDetectTimestampRef = useRef(0)
    const detectErrorCountRef = useRef(0)
    const detectModeRef = useRef<'video' | 'image'>('video')
    const fallbackCanvasRef = useRef<HTMLCanvasElement | null>(null)
    const fallbackCtxRef = useRef<CanvasRenderingContext2D | null>(null)

    const resetRuntimeState = () => {
        startedAtRef.current = 0
        sampleCountRef.current = 0
        blinkCountRef.current = 0
        lastBlinkStateRef.current = false
        lastDriftFlagRef.current = false
        driftCountRef.current = 0
        movementWindowRef.current = []
        previousMicroPointsRef.current = null
        blendshapeSumsRef.current = {}
        blendshapeSamplesRef.current = 0
        lastAnalyzeAtRef.current = 0
        lastVideoTimeRef.current = -1
        lastDetectTimestampRef.current = 0
        detectErrorCountRef.current = 0
        detectModeRef.current = 'video'
    }

    const ensureFallbackCanvas = (width: number, height: number) => {
        const safeWidth = Math.max(1, Math.floor(width || 0))
        const safeHeight = Math.max(1, Math.floor(height || 0))

        if (!fallbackCanvasRef.current) {
            const canvas = document.createElement('canvas')
            canvas.width = safeWidth
            canvas.height = safeHeight
            fallbackCanvasRef.current = canvas
            fallbackCtxRef.current = canvas.getContext('2d', { willReadFrequently: true })
        }

        const canvas = fallbackCanvasRef.current
        if (canvas.width !== safeWidth || canvas.height !== safeHeight) {
            canvas.width = safeWidth
            canvas.height = safeHeight
        }

        if (!fallbackCtxRef.current) {
            fallbackCtxRef.current = canvas.getContext('2d', { willReadFrequently: true })
        }

        if (!fallbackCtxRef.current) {
            throw new Error('无法创建 FaceBehavior fallback canvas context')
        }

        return {
            canvas,
            ctx: fallbackCtxRef.current,
        }
    }

    const flushMetrics = (next: FaceBehaviorMetrics, force = false) => {
        const now = performance.now()
        if (!force && now - lastUiUpdateAtRef.current < UI_UPDATE_INTERVAL_MS) {
            return
        }
        lastUiUpdateAtRef.current = now
        setMetrics(next)
    }

    const stopLoop = (nextStatus: FaceMetricStatus, errorMessage?: string) => {
        if (rafIdRef.current !== null) {
            cancelAnimationFrame(rafIdRef.current)
            rafIdRef.current = null
        }
        resetRuntimeState()
        flushMetrics({
            ...EMPTY_METRICS,
            status: nextStatus,
            error: errorMessage,
        }, true)
    }

    const ensureLandmarker = async (): Promise<FaceLandmarker> => {
        if (landmarkerRef.current) return landmarkerRef.current
        if (!landmarkerPromiseRef.current) {
            landmarkerPromiseRef.current = (async () => {
                const visionModule = await import(
                    /* webpackIgnore: true */
                    'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/+esm'
                ) as unknown as VisionModule
                const vision = await visionModule.FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_URL)
                try {
                    return await visionModule.FaceLandmarker.createFromOptions(vision, {
                        baseOptions: {
                            modelAssetPath: FACE_LANDMARKER_MODEL_URL,
                            delegate: 'GPU',
                        },
                        runningMode: 'VIDEO',
                        numFaces: 2,
                        outputFaceBlendshapes: true,
                        outputFacialTransformationMatrixes: true,
                    })
                } catch {
                    return visionModule.FaceLandmarker.createFromOptions(vision, {
                        baseOptions: {
                            modelAssetPath: FACE_LANDMARKER_MODEL_URL,
                            delegate: 'CPU',
                        },
                        runningMode: 'VIDEO',
                        numFaces: 2,
                        outputFaceBlendshapes: true,
                        outputFacialTransformationMatrixes: true,
                    })
                }
            })()
        }
        landmarkerRef.current = await landmarkerPromiseRef.current
        return landmarkerRef.current
    }

    const processFrame = (landmarker: FaceLandmarker): FaceBehaviorMetrics => {
        const video = videoRef.current
        if (!video || video.readyState < 2 || video.videoWidth === 0 || video.videoHeight === 0) {
            return {
                ...EMPTY_METRICS,
                status: 'loading',
            }
        }

        const now = performance.now()
        if (lastAnalyzeAtRef.current > 0 && now - lastAnalyzeAtRef.current < ANALYZE_FRAME_INTERVAL_MS) {
            return metrics
        }

        // 对视频模式推理，优先使用视频时间作为输入时间戳，并保证严格单调递增。
        const currentVideoTime = Number(video.currentTime || 0)
        if (currentVideoTime === lastVideoTimeRef.current && lastAnalyzeAtRef.current > 0) {
            return metrics
        }

        let detectTimestamp = Math.round(currentVideoTime * 1000)
        if (!Number.isFinite(detectTimestamp) || detectTimestamp <= 0) {
            detectTimestamp = Math.round(now)
        }
        if (detectTimestamp <= lastDetectTimestampRef.current) {
            detectTimestamp = lastDetectTimestampRef.current + 1
        }

        lastAnalyzeAtRef.current = now

        const detectWithVideoMode = () => {
            return withFilteredDelegateLogs(() => landmarker.detectForVideo(video, detectTimestamp))
        }

        const detectWithImageMode = () => {
            if (typeof landmarker.detect !== 'function') {
                throw new Error('FaceLandmarker.detect 不可用，无法切换 IMAGE 模式')
            }
            const { canvas, ctx } = ensureFallbackCanvas(video.videoWidth, video.videoHeight)
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
            return withFilteredDelegateLogs(() => landmarker.detect!(canvas))
        }

        let result: FaceLandmarkerResult
        try {
            if (detectModeRef.current === 'video') {
                result = detectWithVideoMode()
            } else {
                result = detectWithImageMode()
            }
            lastDetectTimestampRef.current = detectTimestamp
            lastVideoTimeRef.current = currentVideoTime
            detectErrorCountRef.current = 0
        } catch (error) {
            detectErrorCountRef.current += 1
            const message = error instanceof Error ? error.message : String(error)

            // VIDEO 模式不稳定时自动降级到 IMAGE 模式，优先保障指标连续可用。
            if (detectModeRef.current === 'video' && detectErrorCountRef.current >= 2) {
                detectModeRef.current = 'image'
                try {
                    result = detectWithImageMode()
                    lastDetectTimestampRef.current = detectTimestamp
                    lastVideoTimeRef.current = currentVideoTime
                    detectErrorCountRef.current = 0
                    console.warn('[FaceBehaviorMetrics] detectForVideo 不稳定，已自动降级到 IMAGE 模式')
                } catch (fallbackError) {
                    const fallbackMessage = fallbackError instanceof Error ? fallbackError.message : String(fallbackError)
                    if (detectErrorCountRef.current <= 3) {
                        console.warn('[FaceBehaviorMetrics] IMAGE 模式回退失败：', fallbackMessage)
                    }
                    if (detectErrorCountRef.current >= 12) {
                        return {
                            ...EMPTY_METRICS,
                            status: 'error',
                            error: `FaceLandmarker 推理连续失败: ${fallbackMessage}`,
                        }
                    }
                    return {
                        ...metrics,
                        status: metrics.status === 'idle' ? 'loading' : metrics.status,
                    }
                }
            } else {
                if (detectErrorCountRef.current <= 3) {
                    console.warn('[FaceBehaviorMetrics] detectForVideo 单帧推理失败，已跳过该帧：', message)
                }

                if (detectErrorCountRef.current >= 12) {
                    return {
                        ...EMPTY_METRICS,
                        status: 'error',
                        error: `FaceLandmarker 推理连续失败: ${message}`,
                    }
                }
                return {
                    ...metrics,
                    status: metrics.status === 'idle' ? 'loading' : metrics.status,
                }
            }
        }

        const allFaces = Array.isArray(result?.faceLandmarks) ? result.faceLandmarks : []
        const faceCount = allFaces.length
        const hasFace = faceCount > 0

        if (!hasFace) {
            previousMicroPointsRef.current = null
            lastBlinkStateRef.current = false
            lastDriftFlagRef.current = false
            return {
                ...metrics,
                status: 'no_face',
                hasFace: false,
                faceCount: 0,
            }
        }

        if (!startedAtRef.current) startedAtRef.current = Date.now()
        sampleCountRef.current += 1

        const landmarks = allFaces[0] || []
        const landmarkCount = landmarks.length

        const mouthUpper = landmarks[MOUTH_UPPER_LIP_INDEX]
        const mouthLower = landmarks[MOUTH_LOWER_LIP_INDEX]
        const mouthLeft = landmarks[MOUTH_LEFT_CORNER_INDEX]
        const mouthRight = landmarks[MOUTH_RIGHT_CORNER_INDEX]
        const mouthOpen = distance2d(mouthUpper, mouthLower)
        const mouthWidth = Math.max(1e-6, distance2d(mouthLeft, mouthRight))
        const mouthOpenRatio = roundNum(mouthOpen / mouthWidth, 4)

        const currentMicroPoints = MICRO_MOVEMENT_INDICES
            .map((index) => landmarks[index])
            .filter((pt): pt is Point3D => Boolean(pt && Number.isFinite(pt.x) && Number.isFinite(pt.y)))

        if (previousMicroPointsRef.current && currentMicroPoints.length === previousMicroPointsRef.current.length && currentMicroPoints.length > 0) {
            const displacement = currentMicroPoints.reduce((acc, pt, index) => {
                const prev = previousMicroPointsRef.current?.[index]
                return acc + distance2d(pt, prev)
            }, 0) / currentMicroPoints.length
            const window = movementWindowRef.current
            window.push(displacement)
            if (window.length > 64) window.shift()
        }
        previousMicroPointsRef.current = currentMicroPoints
        const microMovementVariance = roundNum(variance(movementWindowRef.current), 6)

        const faceDistancePoint = avgPoint(landmarks, FACE_DISTANCE_INDICES)
        const faceDistanceZ = roundNum(faceDistancePoint?.z, 6)

        const blendshapeMap = extractBlendshapeMap(result?.faceBlendshapes?.[0]?.categories)
        const blendshapeNames = Object.keys(blendshapeMap)
        if (blendshapeNames.length > 0) {
            blendshapeSamplesRef.current += 1
            for (const name of blendshapeNames) {
                blendshapeSumsRef.current[name] = (blendshapeSumsRef.current[name] || 0) + blendshapeMap[name]
            }
        }

        const leftBlink = (blendshapeMap.eyeBlinkLeft || 0) >= BLINK_THRESHOLD
        const rightBlink = (blendshapeMap.eyeBlinkRight || 0) >= BLINK_THRESHOLD
        const blinkClosed = leftBlink || rightBlink
        if (blinkClosed && !lastBlinkStateRef.current) {
            blinkCountRef.current += 1
        }
        lastBlinkStateRef.current = blinkClosed

        const elapsedMinutes = startedAtRef.current ? Math.max((Date.now() - startedAtRef.current) / 60000, 1e-6) : 1
        const blinkRatePerMin = roundNum(blinkCountRef.current / elapsedMinutes, 2)

        const averages: Record<string, number> = {}
        if (blendshapeSamplesRef.current > 0) {
            for (const [name, sum] of Object.entries(blendshapeSumsRef.current)) {
                averages[name] = roundNum(sum / blendshapeSamplesRef.current, 4) || 0
            }
        }

        const smileCurrent = ((blendshapeMap.mouthSmileLeft || 0) + (blendshapeMap.mouthSmileRight || 0)) / 2
        const smileAvg = roundNum(((averages.mouthSmileLeft || 0) + (averages.mouthSmileRight || 0)) / 2, 4)
        const browInnerUpAvg = roundNum(averages.browInnerUp || blendshapeMap.browInnerUp || 0, 4)
        const jawOpenAvg = roundNum(averages.jawOpen || blendshapeMap.jawOpen || 0, 4)

        const keyCurrent: Record<string, number> = {}
        for (const key of KEY_BLENDSHAPE_NAMES) {
            keyCurrent[key] = roundNum(blendshapeMap[key] || 0, 4) || 0
        }
        keyCurrent.mouthSmileAvg = roundNum(smileCurrent, 4) || 0

        const headPose = extractEulerAngles(result?.facialTransformationMatrixes?.[0]?.data)

        const leftIris = avgPoint(landmarks, LEFT_IRIS_INDICES)
        const rightIris = avgPoint(landmarks, RIGHT_IRIS_INDICES)
        const leftEyeOuter = landmarks[LEFT_EYE_OUTER_INDEX]
        const leftEyeInner = landmarks[LEFT_EYE_INNER_INDEX]
        const rightEyeOuter = landmarks[RIGHT_EYE_OUTER_INDEX]
        const rightEyeInner = landmarks[RIGHT_EYE_INNER_INDEX]

        const leftEyeCenter = avgPoint(landmarks, [LEFT_EYE_OUTER_INDEX, LEFT_EYE_INNER_INDEX])
        const rightEyeCenter = avgPoint(landmarks, [RIGHT_EYE_OUTER_INDEX, RIGHT_EYE_INNER_INDEX])
        const leftEyeWidth = Math.max(1e-6, distance2d(leftEyeOuter, leftEyeInner))
        const rightEyeWidth = Math.max(1e-6, distance2d(rightEyeOuter, rightEyeInner))

        const leftOffsetX = leftIris && leftEyeCenter ? (leftIris.x - leftEyeCenter.x) / leftEyeWidth : 0
        const rightOffsetX = rightIris && rightEyeCenter ? (rightIris.x - rightEyeCenter.x) / rightEyeWidth : 0
        const leftOffsetY = leftIris && leftEyeCenter ? (leftIris.y - leftEyeCenter.y) / leftEyeWidth : 0
        const rightOffsetY = rightIris && rightEyeCenter ? (rightIris.y - rightEyeCenter.y) / rightEyeWidth : 0

        const gazeOffset: GazeOffset = {
            x: (leftOffsetX + rightOffsetX) / 2,
            y: (leftOffsetY + rightOffsetY) / 2,
            magnitude: Math.hypot((leftOffsetX + rightOffsetX) / 2, (leftOffsetY + rightOffsetY) / 2),
        }
        const gazeDriftFlag = gazeOffset.magnitude >= GAZE_DRIFT_THRESHOLD
        if (gazeDriftFlag && !lastDriftFlagRef.current) {
            driftCountRef.current += 1
        }
        lastDriftFlagRef.current = gazeDriftFlag

        const gazeFocusScore = roundNum(clamp(100 - gazeOffset.magnitude * 220, 0, 100), 2)

        return {
            status: 'tracking',
            hasFace,
            faceCount,
            sampleCount: sampleCountRef.current,
            landmarks3d: {
                landmark_count: landmarkCount,
                mouth_open_ratio: mouthOpenRatio,
                micro_movement_variance: microMovementVariance,
                face_distance_z: faceDistanceZ,
            },
            blendshapes: {
                available_count: blendshapeNames.length,
                key_current: keyCurrent,
                averages,
                blink_rate_per_min: blinkRatePerMin,
                brow_inner_up_avg: browInnerUpAvg,
                smile_avg: smileAvg,
                jaw_open_avg: jawOpenAvg,
            },
            headPose: headPose
                ? {
                    pitch: roundNum(headPose.pitch, 2) || 0,
                    yaw: roundNum(headPose.yaw, 2) || 0,
                    roll: roundNum(headPose.roll, 2) || 0,
                }
                : null,
            irisTracking: {
                gaze_offset_x: roundNum(gazeOffset.x, 4),
                gaze_offset_y: roundNum(gazeOffset.y, 4),
                gaze_offset_magnitude: roundNum(gazeOffset.magnitude, 4),
                gaze_focus_score: gazeFocusScore,
                drift_count: driftCountRef.current,
            },
            error: undefined,
        }
    }

    useEffect(() => {
        if (!enabled) {
            sessionIdRef.current += 1
            stopLoop('idle')
            return
        }

        const currentSessionId = sessionIdRef.current + 1
        sessionIdRef.current = currentSessionId
        let cancelled = false

        const loop = async () => {
            if (cancelled || sessionIdRef.current !== currentSessionId) return

            try {
                const landmarker = await ensureLandmarker()
                if (cancelled || sessionIdRef.current !== currentSessionId) return
                const next = processFrame(landmarker)
                flushMetrics(next)
            } catch (error) {
                const message = error instanceof Error ? error.message : 'FaceLandmarker 处理失败'
                stopLoop('error', message)
                return
            }

            rafIdRef.current = requestAnimationFrame(loop)
        }

        flushMetrics({ ...EMPTY_METRICS, status: 'loading' }, true)
        rafIdRef.current = requestAnimationFrame(loop)

        return () => {
            cancelled = true
            if (rafIdRef.current !== null) {
                cancelAnimationFrame(rafIdRef.current)
                rafIdRef.current = null
            }
            resetRuntimeState()
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [enabled])

    useEffect(() => {
        return () => {
            sessionIdRef.current += 1
            if (rafIdRef.current !== null) {
                cancelAnimationFrame(rafIdRef.current)
                rafIdRef.current = null
            }
            landmarkerRef.current?.close?.()
            landmarkerRef.current = null
            landmarkerPromiseRef.current = null
            resetRuntimeState()
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    return metrics
}

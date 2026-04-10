'use client'

import Link from 'next/link'
import { Suspense, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useSearchParams } from 'next/navigation'
import {
    AlertCircle,
    ArrowRight,
    BarChart3,
    Camera,
    Clock3,
    Eye,
    Gauge,
    MessageSquare,
    Mic,
    ShieldCheck,
    Target,
    TrendingUp,
    Users,
    Volume2,
} from 'lucide-react'
import {
    CartesianGrid,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
    ReferenceArea,
} from 'recharts'
import PersistentSidebar from '@/components/PersistentSidebar'
import { getBackendBaseUrl } from '@/lib/backend'

const BACKEND_API_BASE = getBackendBaseUrl()

type StructuredDimension = {
    key: string
    label: string
    score: number
}

type RoundAggregationProfile = {
    round_type: string
    turn_count_total: number
    turn_count_used: number
    turn_count_excluded: number
    round_score_raw: number | null
    round_score_stable: number | null
    round_content_score: number | null
    round_delivery_score: number | null
    round_presence_score: number | null
    round_consistency_score: number | null
    confidence_avg: number | null
    relative_position: number | null
    relative_band: string | null
    baseline_avg_score: number | null
    baseline_sample_size: number
    difficulty_adjustment: number
    outlier_turns: Array<{
        turn_id: string
        question_excerpt: string
        raw_score: number
        deviation_from_median: number
        suppression_factor: number
        reason: string
    }>
    excluded_turns: Array<{
        turn_id: string
        status: string
        reason: string
    }>
    status_mix: Record<string, number>
}

type ConfidenceBreakdown = {
    data_confidence?: number | null
    model_confidence?: number | null
    rubric_confidence?: number | null
    overall_confidence?: number | null
    sample_size?: number
}

type EvaluationV2Layer = {
    overall_score?: number | null
    sample_size?: number
    confidence_breakdown?: ConfidenceBreakdown
}

type ImmediateReport = {
    interview_id: string
    summary: {
        duration_seconds: number
        dialogue_count?: number
    }
    anti_cheat: {
        risk_level: string
        max_probability: number
        avg_probability: number
        events_count: number
        event_type_breakdown?: EventTypeCount[]
        top_risk_events?: RiskEvent[]
        statistics?: CameraStatistics
    }
    structured_evaluation: {
        status: string
        status_message: string
        overall_score: number | null
        level: string | null
        total_questions?: number
        evaluated_questions?: number
        round_breakdown?: Array<{
            round_type: string
            count: number
            avg_score: number
        }>
        round_aggregation?: {
            status: string
            status_message?: string
            round_profiles: RoundAggregationProfile[]
            round_summary?: {
                total_rounds: number
                ready_rounds: number
                total_turns_used: number
                total_turns_excluded: number
                dominant_round_type: string | null
                status_mix?: Record<string, number>
            }
            interview_stability: {
                overall_score_raw: number | null
                overall_score_stable: number | null
                round_count: number
                avg_consistency_score: number | null
                outlier_turn_count: number
                dominant_round_type: string | null
            }
            calibration_version?: string
            stabilizer_version?: string
        }
        dimension_scores: StructuredDimension[]
    }
    evaluation_v2?: {
        status: string
        status_message?: string
        total_questions?: number
        evaluated_questions?: number
        layers?: Record<string, EvaluationV2Layer>
        fusion?: {
            overall_score?: number | null
            overall_confidence?: number | null
            formula?: string
            axis_confidence_breakdowns?: Record<string, ConfidenceBreakdown>
        }
    }
    content_performance?: ContentPerformance
    speech_performance?: SpeechPerformance
    camera_performance?: CameraPerformance
    next_steps?: {
        replay_url?: string
    }
}

type RiskEvent = {
    event_type: string
    score: number
    description: string
    timestamp: number
}

type EventTypeCount = {
    event_type: string
    count: number
}

type CameraStatistics = {
    total_deviations: number
    total_mouth_open: number
    total_multi_person: number
    off_screen_ratio: number
    frames_processed?: number
}

type CameraInsights = {
    sample_count?: number
    landmarks_3d?: {
        avg_landmark_count?: number
        max_landmark_count?: number
        avg_mouth_open_ratio?: number
        avg_micro_movement_variance?: number
        avg_face_distance_z?: number
        close_ratio?: number
        far_ratio?: number
    }
    blendshapes?: {
        tracked_count_max?: number
        avg_blink_rate_per_min?: number
        avg_brow_inner_up?: number
        avg_smile?: number
        avg_jaw_open?: number
        avg_speech_expressiveness?: number
        blendshape_averages?: Record<string, number>
    }
    head_pose?: {
        avg_abs_pitch?: number
        avg_abs_yaw?: number
        avg_abs_roll?: number
        high_pose_ratio?: number
    }
    iris_tracking?: {
        avg_gaze_offset_magnitude?: number
        avg_gaze_focus_score?: number
        max_drift_count?: number
        drift_jumps?: number
    }
    gaze_focus_summary?: {
        avg_focus_score?: number
        low_focus_ratio?: number
        min_focus_score?: number
    }
    gaze_focus_trend?: Array<{
        second?: number
        focus_score?: number
        off_screen_ratio?: number
        risk_score?: number
    }>
}

type WeakDimension = {
    key: string
    label: string
    avg_score: number
    sample_count: number
    reasons: string[]
    reason_tags?: string[]
}

type QuestionEvidence = {
    turn_id: string
    round_type: string
    question_excerpt: string
    answer_excerpt: string
    overall_score: number
    weak_dimensions: Array<{
        key: string
        label: string
        score: number
        reason: string
        reason_tags?: string[]
    }>
    reason_tags?: string[]
    evidence_tags: string[]
    trace_source: string
}

type ContentPerformance = {
    status: string
    status_message: string
    weak_dimensions: WeakDimension[]
    question_evidence: QuestionEvidence[]
    scoring_basis: {
        overall_formula: string
        question_formula: string
        sample_size: number
    }
}

type SpeechPerformance = {
    status: string
    status_message: string
    dimensions: Array<{
        key: string
        label: string
        score: number
    }>
    summary: {
        avg_speech_rate_wpm?: number
        avg_fillers_per_100_words?: number
        avg_pause_anomaly_ratio?: number
        avg_long_pause_count?: number
        samples?: number
    }
    evidence_samples: Array<{
        turn_id: string
        transcript_excerpt: string
        speech_rate_wpm: number
        fillers_per_100_words: number
        pause_anomaly_ratio: number
        long_pause_count: number
        token_count: number
    }>
    diagnosis: string[]
}

type CameraPerformance = {
    status: string
    status_message: string
    overall_score: number
    focus_score: number
    compliance_score: number
    anti_cheat_score: number
    statistics: CameraStatistics
    camera_insights?: CameraInsights
    event_type_breakdown: EventTypeCount[]
    top_risk_events: RiskEvent[]
    notes: string[]
}

type ApiResult = {
    success: boolean
    report?: ImmediateReport
    error?: string
}

type TurnDimensionEvidence = {
    score?: number
    reason?: string
    evidence?: {
        hit_rubric_points?: string[]
        missed_rubric_points?: string[]
        source_quotes?: string[]
        deduction_rationale?: string
    }
}

type TurnFusion = {
    status?: string
    overall_score?: number | null
    formula?: string
    layer_scores?: Record<string, number>
    effective_weights?: Record<string, number>
    missing_layers?: string[]
    rejection_reasons?: Record<string, string[]>
    calculation_steps?: string[]
}

type TurnEvidenceService = {
    status?: string
    source?: string
    confidence?: number
    quality_gate?: {
        passed?: boolean
        reasons?: string[]
    }
    features?: Record<string, unknown>
    quotes?: string[]
    signals?: Array<{
        code?: string
        severity?: string
        label?: string
        score?: number
    }>
}

type TurnScorecardEvaluation = {
    status?: string
    scoring_snapshot?: Record<string, unknown>
    fusion?: TurnFusion
    text_layer?: {
        evidence_service?: TurnEvidenceService
    }
    speech_layer?: {
        evidence_service?: TurnEvidenceService
    }
    video_layer?: {
        evidence_service?: TurnEvidenceService
    }
    layer2?: {
        dimension_evidence_json?: Record<string, TurnDimensionEvidence>
        summary?: {
            strengths?: string[]
            weaknesses?: string[]
            next_actions?: string[]
        }
    }
}

type TurnTrace = {
    event_type?: string
    status?: string
    duration_ms?: number | null
    created_at?: string
    payload?: Record<string, unknown>
}

type TurnScorecard = {
    interview_id?: string
    turn_id?: string
    evaluation?: TurnScorecardEvaluation
    traces?: TurnTrace[]
    speech_evaluation?: {
        final_transcript?: string
    }
}

type TraceApiResult = {
    success: boolean
    scorecard?: TurnScorecard
    snapshot?: Record<string, unknown>
    trace?: TurnTrace[]
    error?: string
}

type SafeDimensionEvidenceView = {
    key: string
    score: number | null
    reason: string
    hit: string[]
    missed: string[]
    quotes: string[]
    rationale: string
}

type ReadableDimensionNarrative = SafeDimensionEvidenceView & {
    label: string
    scoreValue: number
    overview: string
    highlightText: string
    gapText: string
    evidenceText: string
}

function formatDuration(seconds = 0) {
    const safe = Math.max(0, Math.floor(seconds))
    const min = Math.floor(safe / 60)
    const sec = safe % 60
    return min > 0 ? `${min}分${sec}秒` : `${sec}秒`
}

function roundLabel(roundType: string) {
    const normalized = String(roundType || '').trim().toLowerCase()
    if (normalized === 'technical') return '技术面'
    if (normalized === 'project') return '项目面'
    if (normalized === 'system_design') return '系统设计面'
    if (normalized === 'hr') return 'HR 综合面'
    return normalized ? roundType : '--'
}

function relativeBandLabel(relativeBand: string | null, relativePosition: number | null, sampleSize = 0) {
    if (relativeBand == null || relativePosition == null || sampleSize <= 0) {
        return '样本不足，不做校准判断'
    }
    if (relativeBand === 'above_baseline') {
        return `高于同轮次基线 ${formatNum(relativePosition, 1, '0.0')} 分`
    }
    if (relativeBand === 'below_baseline') {
        return `低于同轮次基线 ${formatNum(Math.abs(relativePosition), 1, '0.0')} 分`
    }
    return '与同轮次基线基本接近'
}

function relativeBandTone(relativeBand: string | null) {
    if (relativeBand === 'above_baseline') return 'bg-[#E7F3EA] text-[#2E6A45]'
    if (relativeBand === 'below_baseline') return 'bg-[#FDECEC] text-[#8A3B3B]'
    if (relativeBand === 'near_baseline') return 'bg-[#F3EFE4] text-[#6A5A2B]'
    return 'bg-[#F2F2F0] text-[#666666]'
}

function riskTone(level: string) {
    const normalized = String(level || '').toUpperCase()
    if (normalized === 'HIGH') return 'bg-[#FCEBE9] text-[#9D3A2E]'
    if (normalized === 'MEDIUM') return 'bg-[#FFF4E5] text-[#8B5E1A]'
    return 'bg-[#EAF5ED] text-[#2F6B45]'
}

function riskHeatColor(score: number) {
    const safeScore = Math.max(0, Math.min(100, Number.isFinite(score) ? score : 0))
    const hue = 140 - (safeScore / 100) * 132
    return `hsl(${hue.toFixed(1)} 58% 46%)`
}

function eventLabel(eventType: string) {
    const normalized = String(eventType || '').toLowerCase()
    if (normalized === 'gaze_deviation') return '视线偏离'
    if (normalized === 'mouth_open') return '异常口型'
    if (normalized === 'multi_person') return '多人同框'
    return normalized || '未知事件'
}

function formatNum(value: unknown, digits = 1, fallback = '--') {
    const num = Number(value)
    return Number.isFinite(num) ? num.toFixed(digits) : fallback
}

function formatConfidencePercent(value: unknown, digits = 0, fallback = '--') {
    const num = Number(value)
    return Number.isFinite(num) ? `${(num * 100).toFixed(digits)}%` : fallback
}

function confidenceAxisLabel(axis: string) {
    const normalized = String(axis || '').trim().toLowerCase()
    if (normalized === 'content') return '内容轴'
    if (normalized === 'delivery') return '表达轴'
    if (normalized === 'presence') return '镜头轴'
    if (normalized === 'text') return '文本层'
    if (normalized === 'speech') return '语音层'
    if (normalized === 'video') return '镜头层'
    return axis || '--'
}

function confidenceAxisDescription(axis: string) {
    const normalized = String(axis || '').trim().toLowerCase()
    if (normalized === 'content') return '看当前内容分是否建立在足够样本、稳定推理和充足证据上。'
    if (normalized === 'delivery') return '看语音表达分是否有足够时长、稳定识别和可靠停顿/流畅度信号支持。'
    if (normalized === 'presence') return '看镜头表现分是否建立在稳定检测、充分帧数和有效视觉信号上。'
    return '用于解释这一轴当前分数为什么可信或为什么需要谨慎解读。'
}

function confidenceTone(value: number | null | undefined) {
    const num = Number(value)
    if (!Number.isFinite(num)) return 'bg-[#F2F2F0] text-[#666666]'
    if (num >= 0.8) return 'bg-[#E7F3EA] text-[#2E6A45]'
    if (num >= 0.6) return 'bg-[#F3EFE4] text-[#6A5A2B]'
    return 'bg-[#FDECEC] text-[#8A3B3B]'
}

function evidenceSourceLabel(source: string | undefined) {
    const normalized = String(source || '').trim().toLowerCase()
    if (normalized === 'text') return '文本证据'
    if (normalized === 'speech') return '语音证据'
    if (normalized === 'video') return '镜头证据'
    return source || '--'
}

function evidenceFeatureLabel(key: string) {
    const map: Record<string, string> = {
        coverage_ratio: '覆盖率',
        covered_points_count: '已命中要点',
        missing_points_count: '缺失要点',
        red_flags_count: '红旗信号',
        audio_duration_ms: '音频时长',
        token_count: 'Token 数',
        speech_rate_score: '语速',
        pause_anomaly_score: '异常停顿',
        filler_frequency_score: '口头词',
        fluency_score: '流畅度',
        clarity_score: '清晰度',
        gaze_focus: '视线聚焦',
        posture_compliance: '姿态稳定',
        face_stability: '人脸稳定',
        expression_naturalness: '表情自然度',
        physiology_stability: '生理稳定度',
        physiology_reliability: '生理可靠性',
    }
    return map[key] || key
}

function formatEvidenceFeatureValue(key: string, value: unknown) {
    const num = Number(value)
    if (!Number.isFinite(num)) return String(value || '--')
    if (key === 'coverage_ratio') return `${(num * 100).toFixed(0)}%`
    if (key === 'audio_duration_ms') return `${Math.round(num / 1000)}s`
    if (key.endsWith('_count')) return String(Math.round(num))
    return formatNum(num)
}

function evidenceSeverityTone(severity: string | undefined) {
    const normalized = String(severity || '').trim().toLowerCase()
    if (normalized === 'critical') return 'bg-[#FDECEC] text-[#8A3B3B]'
    if (normalized === 'high') return 'bg-[#FFF4E5] text-[#8B5E1A]'
    if (normalized === 'medium') return 'bg-[#F3EFE4] text-[#6A5A2B]'
    return 'bg-[#ECEBE8] text-[#565451]'
}

function formatEventTime(value: unknown) {
    const num = Number(value)
    if (!Number.isFinite(num)) return '--'
    if (num > 1_000_000) {
        const date = new Date(num * 1000)
        if (!Number.isNaN(date.getTime())) {
            return date.toLocaleTimeString('zh-CN', { hour12: false })
        }
    }
    return `${num.toFixed(1)} 秒`
}

function formatSecondsLabel(value: unknown) {
    const num = Number(value)
    if (!Number.isFinite(num)) return '--'
    return `${num.toFixed(0)}s`
}

function reasonTagTone(tag: string) {
    if (tag === '技术') return 'bg-[#E7F0FF] text-[#2C4A7A]'
    if (tag === '表达') return 'bg-[#FDEFE5] text-[#8A5425]'
    return 'bg-[#ECEBE8] text-[#565451]'
}

function fallbackDimensionLabel(key: string) {
    const map: Record<string, string> = {
        technical_accuracy: '技术准确性',
        knowledge_depth: '知识深度',
        completeness: '回答完整度',
        logic: '逻辑严谨性',
        job_match: '岗位匹配度',
        authenticity: '项目真实性',
        ownership: '个人承担感',
        technical_depth: '技术深挖程度',
        reflection: '复盘反思能力',
        communication: '沟通表现',
        architecture_reasoning: '架构推演能力',
        tradeoff_awareness: '取舍意识',
        scalability: '可扩展性思考',
        clarity: '表达清晰度',
        relevance: '回答贴题度',
        self_awareness: '自我认知',
        confidence: '职业自信度',
    }
    return map[key] || key
}

function containsLatinLetters(text: string) {
    return /[A-Za-z]/.test(String(text || ''))
}

function preferChineseSummaryLine(text: string) {
    const normalized = String(text || '').trim()
    if (!normalized) return ''
    if (containsLatinLetters(normalized)) return ''
    return normalized
}

function joinReadableItems(items: string[], maxItems = 2) {
    const normalized = items
        .map((item) => String(item || '').trim())
        .filter(Boolean)
        .slice(0, maxItems)
    if (normalized.length === 0) return ''
    if (normalized.length === 1) return normalized[0]
    if (normalized.length === 2) return `${normalized[0]}、${normalized[1]}`
    return `${normalized.slice(0, -1).join('、')} 和 ${normalized[normalized.length - 1]}`
}

function scoreBandText(scoreValue: number) {
    if (scoreValue >= 85) return '已经形成明显优势'
    if (scoreValue >= 70) return '整体比较扎实'
    if (scoreValue >= 55) return '基础已经具备，但还不够稳定'
    return '目前仍是这一题的主要短板'
}

type DimensionNarrator = {
    focusNoun: string
    overviewTemplates: string[]
    strengthTemplates: string[]
    gapTemplates: string[]
    evidenceTemplates: string[]
}

const DEFAULT_DIMENSION_NARRATOR: DimensionNarrator = {
    focusNoun: '这一项能力',
    overviewTemplates: [
        '这一维主要看你的回答有没有把关键点讲清楚',
        '这一维更关注你在该能力上的呈现是否稳定',
    ],
    strengthTemplates: [
        '已经有一些有效内容托住了这一维的基础分',
        '这一维不是完全空白，你已经讲到了一部分关键点',
    ],
    gapTemplates: [
        '真正拉不开分差的地方，还在更具体的展开和落地',
        '接下来要补的，不是再重复一句，而是把关键细节讲透',
    ],
    evidenceTemplates: [
        '系统主要是根据你回答里的具体表述来判断这一维',
        '这一维的评分主要依据还是你当时给出的原始回答内容',
    ],
}

const DIMENSION_NARRATORS: Record<string, DimensionNarrator> = {
    technical_accuracy: {
        focusNoun: '概念是否准确、有没有技术性混淆',
        overviewTemplates: [
            '技术准确性这一维，主要看你有没有把核心概念说对、边界说清',
            '这一维更在意你说出来的技术判断是否准确，是否存在概念混用',
        ],
        strengthTemplates: [
            '比较好的地方在于，你已经抓住了一部分关键技术点，没有明显跑偏',
            '从回答内容看，你对核心概念并不是完全模糊的，基础判断大体在线',
        ],
        gapTemplates: [
            '拉低这一维的，通常不是没提到，而是概念还不够准、原理还不够透',
            '如果想把这项分数继续拉高，需要把术语、原理和适用边界讲得更稳',
        ],
        evidenceTemplates: [
            '这一维主要看你当时对概念、机制和场景的表述是否站得住',
            '系统会重点对照你回答里的技术说法，判断有没有混淆或说浅了',
        ],
    },
    completeness: {
        focusNoun: '回答有没有覆盖关键事实、过程和结果',
        overviewTemplates: [
            '回答完整度这一维，主要看你是不是只答到一半，还是把题干真正接住了',
            '这一维更关注覆盖面，尤其是关键事实、过程和结果有没有交代完整',
        ],
        strengthTemplates: [
            '好的地方是，你已经触到题目的主要部分，不是完全片段式作答',
            '从现有内容看，你至少把一部分关键环节交代出来了，框架没有完全缺失',
        ],
        gapTemplates: [
            '真正拖分的地方在于，关键事实链条还没有补满，导致答案显得留白较多',
            '如果继续优化，这一维最需要的是把背景、动作和结果补成闭环',
        ],
        evidenceTemplates: [
            '系统主要根据你有没有把题目要求的几个关键环节说到位来判断这一维',
            '这一维的依据不是某一句漂亮话，而是整段回答是否形成了完整闭环',
        ],
    },
    logic: {
        focusNoun: '因果链条是否顺，论述推进是否有层次',
        overviewTemplates: [
            '逻辑严谨性这一维，主要看你的回答是不是有清晰的推进顺序和因果关系',
            '这一维更关注你讲述时有没有主线，结论、原因和结果是否连得起来',
        ],
        strengthTemplates: [
            '做得相对好的地方是，回答里还能看出主线，没有完全散掉',
            '至少从表达顺序上看，你不是在堆零散信息，而是有一定组织的',
        ],
        gapTemplates: [
            '这一维没有继续拉高，通常是因为因果关系还不够顺，论证有跳步',
            '接下来更需要补的是推导链，而不是再加一堆平行信息',
        ],
        evidenceTemplates: [
            '系统会重点看你有没有把“为什么这么做、结果怎样、意义是什么”串起来',
            '这一维主要依据回答里的结构感和因果推进来判断，不只是看关键词命中',
        ],
    },
    job_match: {
        focusNoun: '回答是否贴近目标岗位的真实能力语境',
        overviewTemplates: [
            '岗位匹配度这一维，主要看你的回答有没有体现出目标岗位真正关心的能力场景',
            '这一维不只看答得对不对，更看你讲的内容是不是贴近岗位所需的工作语境',
        ],
        strengthTemplates: [
            '比较有帮助的是，你的回答里已经出现了一些与目标岗位相关的语境和能力线索',
            '从现有内容看，这个回答不是完全泛化的，已经能看到一定岗位相关性',
        ],
        gapTemplates: [
            '影响这一维的关键问题，通常是内容还偏泛，没有真正贴到岗位职责和场景上',
            '如果想让岗位匹配度上去，需要把回答往真实工作任务、取舍和结果上再靠近一些',
        ],
        evidenceTemplates: [
            '系统会对照岗位方向，判断你这段回答体现出来的能力是否真的对口',
            '这一维的依据不是单个术语，而是你的经历、方法和场景是否像这个岗位的人在说话',
        ],
    },
    confidence: {
        focusNoun: '表达里的判断感、承担感和稳定度',
        overviewTemplates: [
            '职业自信度这一维，主要看你说话时是否有明确判断，以及能不能稳住自己的角色和选择',
            '这一维关注的不是外向与否，而是你在描述经历、判断和选择时是否足够稳定',
        ],
        strengthTemplates: [
            '已有的正面信号是，你的表达里能看到一定判断感，不是完全飘着说',
            '从回答内容看，你并非完全缺乏自信，至少部分表述是站得住的',
        ],
        gapTemplates: [
            '这一维拉不开，往往不是因为声音大小，而是立场、角色和结论还不够笃定',
            '想把这项提上去，更重要的是把自己的判断、贡献和选择说得更稳一些',
        ],
        evidenceTemplates: [
            '系统主要根据你是否敢于明确表达判断、承担角色和解释选择来判断这一维',
            '这一维看的是语义上的稳定度，而不是音量、语速或外向程度',
        ],
    },
}

function narrativeIndex(seed: string, modulo: number) {
    if (modulo <= 0) return 0
    let hash = 0
    for (let i = 0; i < seed.length; i += 1) {
        hash = (hash * 31 + seed.charCodeAt(i)) >>> 0
    }
    return hash % modulo
}

function pickNarrative(seed: string, templates: string[]) {
    if (!templates.length) return ''
    return templates[narrativeIndex(seed, templates.length)]
}

function cleanNarrativeText(text: string) {
    return String(text || '')
        .trim()
        .replace(/[。；，、\s]+$/g, '')
}

function buildDimensionNarrative(
    item: SafeDimensionEvidenceView,
    label: string,
    answerExcerpt: string,
): ReadableDimensionNarrative {
    const scoreValue = item.score == null ? 0 : Math.max(0, Math.min(100, Number(item.score)))
    const narrator = DIMENSION_NARRATORS[item.key] || DEFAULT_DIMENSION_NARRATOR
    const hitText = joinReadableItems(item.hit, 2)
    const missedText = joinReadableItems(item.missed, 2)
    const quote = cleanNarrativeText(item.quotes[0] || '')
    const shortAnswerExcerpt = cleanNarrativeText(String(answerExcerpt || '').trim().slice(0, 90))
    const reasonText = cleanNarrativeText(item.reason || item.rationale || '')
    const rationaleText = cleanNarrativeText(item.rationale || item.reason || '')
    const seedBase = `${item.key}:${label}:${formatNum(scoreValue)}:${quote}`

    const overviewLead = pickNarrative(`${seedBase}:overview`, narrator.overviewTemplates)
    const strengthLead = pickNarrative(`${seedBase}:strength`, narrator.strengthTemplates)
    const gapLead = pickNarrative(`${seedBase}:gap`, narrator.gapTemplates)
    const evidenceLead = pickNarrative(`${seedBase}:evidence`, narrator.evidenceTemplates)

    const overview = [
        overviewLead,
        `本题的${label}是 ${formatNum(scoreValue)} 分，${scoreBandText(scoreValue)}`,
        reasonText,
    ].filter(Boolean).join('。') + '。'

    const highlightText = hitText
        ? `${strengthLead}，像 ${hitText} 这些点已经被你明确讲到了。`
        : scoreValue >= 70
            ? `${strengthLead}，虽然系统没有提炼出特别具体的命中点，但整体表达仍然给出了较稳定的正向信号。`
            : `${strengthLead}，只是当前这题里还没有提炼出特别突出的强项证据。`

    const gapText = missedText
        ? `${gapLead}，尤其是 ${missedText} 这部分还没有真正展开。`
        : `${gapLead}，${rationaleText || '建议把关键事实、判断依据和结果再补具体一些。'}。`

    const evidenceText = quote
        ? `${evidenceLead}。像“${quote}”这句，就是本维度判断时最直接的文本依据之一。`
        : shortAnswerExcerpt
            ? `${evidenceLead}。结合你当时的回答“${shortAnswerExcerpt}${shortAnswerExcerpt.length >= 90 ? '…' : ''}”，系统主要据此做出这一维判断。`
            : `${evidenceLead}。当前这题没有抽出更具体的原句，所以解释会相对保守。`

    return {
        ...item,
        label,
        scoreValue,
        overview,
        highlightText,
        gapText,
        evidenceText,
    }
}

function ReportPageContent() {
    const searchParams = useSearchParams()
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [report, setReport] = useState<ImmediateReport | null>(null)
    const [activeTurnId, setActiveTurnId] = useState('')
    const [scorecardLoading, setScorecardLoading] = useState(false)
    const [scorecardError, setScorecardError] = useState('')
    const [activeScorecard, setActiveScorecard] = useState<TurnScorecard | null>(null)
    const [scorecardCache, setScorecardCache] = useState<Record<string, TurnScorecard>>({})
    const [scorecardRetryNonce, setScorecardRetryNonce] = useState(0)
    const interviewId = (searchParams.get('interviewId') || '').trim()

    useEffect(() => {
        const load = async () => {
            try {
                setLoading(true)
                setError('')
                const endpoint = interviewId
                    ? `${BACKEND_API_BASE}/api/report/interview/${encodeURIComponent(interviewId)}`
                    : `${BACKEND_API_BASE}/api/report/latest`
                const res = await fetch(endpoint, { cache: 'no-store' })
                const data: ApiResult = await res.json()
                if (!res.ok || !data.success || !data.report) {
                    throw new Error(data.error || '获取报告失败')
                }
                setReport(data.report)
            } catch (e) {
                setReport(null)
                setError(e instanceof Error ? e.message : '获取报告失败')
            } finally {
                setLoading(false)
            }
        }
        void load()
    }, [interviewId])

    const questionEvidenceList = report?.content_performance?.question_evidence || []

    useEffect(() => {
        if (!questionEvidenceList.length) {
            setActiveTurnId('')
            setActiveScorecard(null)
            setScorecardError('')
            return
        }
        const exists = questionEvidenceList.some((item) => String(item.turn_id || '').trim() === activeTurnId)
        if (!exists) {
            const firstValidTurn = questionEvidenceList.find((item) => String(item.turn_id || '').trim())
            setActiveTurnId(String(firstValidTurn?.turn_id || questionEvidenceList[0]?.turn_id || '').trim())
        }
    }, [questionEvidenceList, activeTurnId])

    useEffect(() => {
        setScorecardCache({})
        setActiveScorecard(null)
        setScorecardError('')
    }, [report?.interview_id])

    useEffect(() => {
        const normalizedInterviewId = String(report?.interview_id || '').trim()
        const normalizedTurnId = String(activeTurnId || '').trim()
        if (!normalizedInterviewId) {
            setScorecardLoading(false)
            return
        }
        if (!normalizedTurnId) {
            setActiveScorecard(null)
            setScorecardLoading(false)
            setScorecardError(questionEvidenceList.length > 0 ? '当前题目缺少 turn_id，无法查询证据链。' : '')
            return
        }

        const cached = scorecardCache[normalizedTurnId]
        if (cached) {
            setActiveScorecard(cached)
            setScorecardLoading(false)
            setScorecardError('')
            return
        }

        let canceled = false
        const loadScorecard = async () => {
            try {
                setScorecardLoading(true)
                setScorecardError('')

                const endpoint = `${BACKEND_API_BASE}/api/evaluation/trace/${encodeURIComponent(normalizedInterviewId)}/${encodeURIComponent(normalizedTurnId)}`
                const res = await fetch(endpoint, { cache: 'no-store' })
                const data: TraceApiResult = await res.json()
                if (!res.ok || !data.success || !data.scorecard) {
                    throw new Error(data.error || '获取单题证据链失败')
                }

                const mergedScorecard: TurnScorecard = {
                    ...(data.scorecard || {}),
                    traces: (data.trace || data.scorecard.traces || []),
                }
                if (canceled) return
                setActiveScorecard(mergedScorecard)
                setScorecardCache((prev) => ({ ...prev, [normalizedTurnId]: mergedScorecard }))
            } catch (e) {
                if (canceled) return
                setActiveScorecard(null)
                setScorecardError(e instanceof Error ? e.message : '获取单题证据链失败')
            } finally {
                if (!canceled) setScorecardLoading(false)
            }
        }

        void loadScorecard()
        return () => {
            canceled = true
        }
    }, [activeTurnId, report?.interview_id, scorecardCache, scorecardRetryNonce, questionEvidenceList.length])

    const radarDimensions = useMemo(() => {
        const weakSource = (report?.content_performance?.weak_dimensions || []).slice(0, 5)
        if (weakSource.length > 0) {
            return weakSource.map((item) => ({
                key: item.key,
                label: item.label,
                score: Number(item.avg_score || 0),
            }))
        }
        return (report?.structured_evaluation?.dimension_scores || []).slice(0, 5).map((item) => ({
            key: item.key,
            label: item.label,
            score: Number(item.score || 0),
        }))
    }, [report])

    const speechRadarDimensions = useMemo(() => {
        return (report?.speech_performance?.dimensions || []).map((item) => ({
            key: item.key,
            label: item.label,
            score: Number(item.score || 0),
        }))
    }, [report])

    const speechWeakItems = useMemo(() => {
        const sorted = [...(report?.speech_performance?.dimensions || [])]
            .map((item) => ({ ...item, score: Number(item.score || 0) }))
            .sort((a, b) => a.score - b.score)

        const belowTarget = sorted.filter((item) => item.score < 75)
        if (belowTarget.length > 0) return belowTarget.slice(0, 3)
        return sorted.slice(0, 2)
    }, [report])

    const dimensionLabelMap = useMemo(() => {
        const map: Record<string, string> = {}
            ; (report?.structured_evaluation?.dimension_scores || []).forEach((item) => {
                if (item?.key) map[item.key] = item.label
            })
            ; (report?.content_performance?.weak_dimensions || []).forEach((item) => {
                if (item?.key) map[item.key] = item.label
            })
        return map
    }, [report])

    const activeDimensionEvidenceList = useMemo<SafeDimensionEvidenceView[]>(() => {
        const source = activeScorecard?.evaluation?.layer2?.dimension_evidence_json || {}
        const entries: SafeDimensionEvidenceView[] = []
        for (const [key, value] of Object.entries(source)) {
            const payload = (value && typeof value === 'object') ? value as TurnDimensionEvidence : {}
            const evidenceObj = (payload.evidence && typeof payload.evidence === 'object') ? payload.evidence : {}
            const scoreNum = Number(payload.score)
            const score = Number.isFinite(scoreNum) ? scoreNum : null
            const reason = String(payload.reason || '').trim()
            const hit = Array.isArray(evidenceObj.hit_rubric_points)
                ? evidenceObj.hit_rubric_points.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
                : []
            const missed = Array.isArray(evidenceObj.missed_rubric_points)
                ? evidenceObj.missed_rubric_points.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
                : []
            const quotes = Array.isArray(evidenceObj.source_quotes)
                ? evidenceObj.source_quotes.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
                : []
            const rationale = String(evidenceObj.deduction_rationale || reason).trim()
            entries.push({
                key,
                score,
                reason,
                hit,
                missed,
                quotes,
                rationale,
            })
        }
        return entries
    }, [activeScorecard])

    const activeQuestionEvidence = useMemo(() => {
        const normalizedTurnId = String(activeTurnId || '').trim()
        if (!questionEvidenceList.length) return null
        if (normalizedTurnId) {
            const matched = questionEvidenceList.find((item) => String(item.turn_id || '').trim() === normalizedTurnId)
            if (matched) return matched
        }
        return questionEvidenceList[0]
    }, [questionEvidenceList, activeTurnId])
    const activeQuestionIndex = useMemo(() => {
        if (!activeQuestionEvidence) return -1
        return questionEvidenceList.findIndex((item) => String(item.turn_id || '').trim() === String(activeQuestionEvidence.turn_id || '').trim())
    }, [questionEvidenceList, activeQuestionEvidence])

    const activeLayer2Summary = useMemo(() => {
        return activeScorecard?.evaluation?.layer2?.summary || null
    }, [activeScorecard])

    const readableDimensionCards = useMemo<ReadableDimensionNarrative[]>(() => {
        return [...activeDimensionEvidenceList]
            .sort((a, b) => Number(a.score ?? 0) - Number(b.score ?? 0))
            .slice(0, 4)
            .map((item) => buildDimensionNarrative(
                item,
                dimensionLabelMap[item.key] || fallbackDimensionLabel(item.key),
                activeQuestionEvidence?.answer_excerpt || '',
            ))
    }, [activeDimensionEvidenceList, dimensionLabelMap, activeQuestionEvidence])

    const weakestDimensionLabel = readableDimensionCards[0]?.label || '--'
    const primaryImprovementAdvice = readableDimensionCards[0]?.gapText || '建议先梳理回答结构，再补充关键细节。'
    const activeQuestionSummary = useMemo(() => {
        const scoreText = formatNum(activeScorecard?.evaluation?.fusion?.overall_score ?? activeQuestionEvidence?.overall_score)
        const topStrength = preferChineseSummaryLine(activeLayer2Summary?.strengths?.[0] || '') || readableDimensionCards.find((item) => item.hit.length > 0)?.highlightText || ''
        const topWeakness = preferChineseSummaryLine(activeLayer2Summary?.weaknesses?.[0] || '') || readableDimensionCards[0]?.gapText || ''
        const topAction = preferChineseSummaryLine(activeLayer2Summary?.next_actions?.[0] || '') || primaryImprovementAdvice
        return [
            `本题整体得分 ${scoreText}，${weakestDimensionLabel !== '--' ? `当前最需要优先补强的是${weakestDimensionLabel}。` : '这道题还有明显的提升空间。'}`,
            topStrength ? `从已有内容看，比较好的部分是：${topStrength}` : '',
            topWeakness ? `拉低得分的主要原因是：${topWeakness}` : '',
            topAction ? `如果继续追问，最值得优先补上的会是：${topAction}` : '',
        ].filter(Boolean)
    }, [activeQuestionEvidence, activeScorecard, activeLayer2Summary, readableDimensionCards, weakestDimensionLabel, primaryImprovementAdvice])

    const activeEvidenceServices = useMemo(() => {
        const evaluation = activeScorecard?.evaluation
        if (!evaluation) return []
        return [
            evaluation.text_layer?.evidence_service,
            evaluation.speech_layer?.evidence_service,
            evaluation.video_layer?.evidence_service,
        ].filter((item): item is TurnEvidenceService => Boolean(item?.source))
    }, [activeScorecard])

    const gazeTrendData = useMemo(() => {
        const source = report?.camera_performance?.camera_insights?.gaze_focus_trend || []
        return source
            .map((item) => {
                const second = Number(item.second)
                const focus = Number(item.focus_score)
                const offscreen = Number(item.off_screen_ratio)
                const risk = Number(item.risk_score)
                return {
                    second: Number.isFinite(second) ? second : 0,
                    focus: Number.isFinite(focus) ? Math.max(0, Math.min(100, focus)) : 0,
                    offscreen: Number.isFinite(offscreen) ? Math.max(0, Math.min(100, offscreen)) : 0,
                    risk: Number.isFinite(risk) ? Math.max(0, Math.min(100, risk)) : 0,
                }
            })
            .sort((a, b) => a.second - b.second)
    }, [report])

    const gazeTrendValleys = useMemo(() => {
        return [...gazeTrendData]
            .sort((a, b) => a.focus - b.focus)
            .slice(0, 3)
    }, [gazeTrendData])

    const refreshActiveTurnAudit = () => {
        const normalizedTurnId = String(activeTurnId || '').trim()
        if (!normalizedTurnId) return
        setScorecardCache((prev) => {
            const next = { ...prev }
            delete next[normalizedTurnId]
            return next
        })
        setScorecardRetryNonce((prev) => prev + 1)
    }

    if (loading) {
        return (
            <div className="flex min-h-screen">
                <PersistentSidebar />
                <main className="flex-1 overflow-y-auto">
                    <div className="mx-auto max-w-4xl px-6 py-8">
                        <section className="rounded-2xl border border-[#E5E5E5] bg-white p-8 text-center shadow-sm">
                            <p className="text-sm text-[#666666]">报告加载中...</p>
                        </section>
                    </div>
                </main>
            </div>
        )
    }

    if (error || !report) {
        return (
            <div className="flex min-h-screen">
                <PersistentSidebar />
                <main className="flex-1 overflow-y-auto">
                    <div className="mx-auto max-w-4xl px-6 py-8">
                        <section className="rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                            <div className="flex items-center gap-2 text-[#8A3B3B]"><AlertCircle className="h-5 w-5" />报告加载失败</div>
                            <p className="mt-2 text-sm text-[#666666]">{error || '未知错误'}</p>
                            <div className="mt-4 flex flex-wrap gap-3">
                                <Link href="/history" className="inline-flex items-center gap-2 rounded-lg border border-[#E5E5E5] px-4 py-2 text-sm font-medium text-[#111111] hover:bg-[#F5F5F5]">
                                    返回历史记录
                                </Link>
                            </div>
                        </section>
                    </div>
                </main>
            </div>
        )
    }

    const replayUrl = report.next_steps?.replay_url || `/replay?interviewId=${encodeURIComponent(report.interview_id)}`
    const contentPerf = report.content_performance
    const speechPerf = report.speech_performance
    const cameraPerf = report.camera_performance
    const cameraStats = cameraPerf?.statistics || report.anti_cheat.statistics
    const cameraInsights = cameraPerf?.camera_insights
    const cameraLandmarks = cameraInsights?.landmarks_3d
    const cameraBlendshape = cameraInsights?.blendshapes
    const cameraHeadPose = cameraInsights?.head_pose
    const cameraIris = cameraInsights?.iris_tracking
    const cameraBreakdown = cameraPerf?.event_type_breakdown || report.anti_cheat.event_type_breakdown || []
    const cameraTopEvents = cameraPerf?.top_risk_events || report.anti_cheat.top_risk_events || []
    const topBlendshapeAverages = Object.entries(cameraBlendshape?.blendshape_averages || {})
        .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0))
        .slice(0, 8)
    const riskPeak = Number(report.anti_cheat.max_probability || 0)
    const riskAverage = Number(report.anti_cheat.avg_probability || 0)
    const riskHeatValue = Math.max(0, Math.min(100, riskPeak * 0.7 + riskAverage * 0.3))
    const riskHeatFillStyle = {
        width: `${riskHeatValue}%`,
        background: `linear-gradient(90deg, ${riskHeatColor(Math.max(riskHeatValue - 18, 0))}, ${riskHeatColor(riskHeatValue)})`,
    }
    const roundBreakdown = report.structured_evaluation.round_breakdown || []
    const dominantRound = [...roundBreakdown].sort((a, b) => Number(b.count || 0) - Number(a.count || 0))[0]?.round_type || ''
    const evaluatedQuestions = Number(report.structured_evaluation.evaluated_questions || 0)
    const totalQuestions = Number(report.structured_evaluation.total_questions || 0)
    const questionProgress = totalQuestions > 0 ? `${evaluatedQuestions}/${totalQuestions}` : String(evaluatedQuestions || report.summary.dialogue_count || 0)
    const roundAggregation = report.structured_evaluation.round_aggregation
    const roundProfiles = roundAggregation?.round_profiles || []
    const roundSummary = roundAggregation?.round_summary
    const interviewStability = roundAggregation?.interview_stability
    const primaryRoundProfile = roundProfiles.length > 0
        ? [...roundProfiles].sort((a, b) => Number(b.turn_count_used || 0) - Number(a.turn_count_used || 0))[0]
        : null
    const primaryRoundWeakestAxis = primaryRoundProfile
        ? [
            { key: 'content', label: '内容轴', score: Number(primaryRoundProfile.round_content_score) },
            { key: 'delivery', label: '表达轴', score: Number(primaryRoundProfile.round_delivery_score) },
            { key: 'presence', label: '镜头轴', score: Number(primaryRoundProfile.round_presence_score) },
        ]
            .filter((item) => Number.isFinite(item.score))
            .sort((a, b) => a.score - b.score)[0] || null
        : null
    const stabilityScore = Number(interviewStability?.avg_consistency_score)
    const stabilitySummaryText = !Number.isFinite(stabilityScore)
        ? '当前样本还不足以给出稳定性判断。'
        : stabilityScore >= 80
            ? '本场回答波动较小，整体发挥比较稳定。'
            : stabilityScore >= 65
                ? '本场整体较稳定，但个别题目的发挥仍有起伏。'
                : stabilityScore >= 50
                    ? '本场表现有明显波动，建议优先加强答题结构的一致性。'
                    : '本场发挥起伏较大，建议先把基础答题节奏和框架稳定下来。'
    const evaluationV2 = report.evaluation_v2
    const confidenceAxes = evaluationV2?.fusion?.axis_confidence_breakdowns || {}
    const contentConfidence = confidenceAxes.content
    const deliveryConfidence = confidenceAxes.delivery
    const presenceConfidence = confidenceAxes.presence
    const hasConfidenceBreakdown = Boolean(contentConfidence || deliveryConfidence || presenceConfidence)
    const reportFusionOverallScore = evaluationV2?.fusion?.overall_score ?? report.structured_evaluation.overall_score
    const displayOverallScore = interviewStability?.overall_score_stable ?? reportFusionOverallScore
    const activeTurnOverallScore = activeScorecard?.evaluation?.fusion?.overall_score ?? activeQuestionEvidence?.overall_score

    return (
        <div className="flex min-h-screen">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-6xl px-6 py-8 space-y-6">
                    <section className="rounded-3xl border border-[#E5E5E5] bg-[#FAF9F6] p-6 shadow-sm sm:p-8">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                            <span className="inline-flex items-center gap-2 rounded-full border border-[#E5E5E5] bg-white px-4 py-2 text-sm text-[#111111]">
                                <ShieldCheck className="h-4 w-4" /> 即时报告
                            </span>
                            <span className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${riskTone(report.anti_cheat.risk_level)}`}>
                                风险 {(report.anti_cheat.risk_level || 'LOW').toUpperCase()}
                            </span>
                        </div>
                        <h1 className="mt-4 text-3xl tracking-tight text-[#111111] sm:text-4xl">本场面试报告</h1>


                        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                            <MetricCard title="综合得分" value={displayOverallScore == null ? '--' : displayOverallScore.toFixed(1)} icon={<Target className="h-3.5 w-3.5" />} />
                            <MetricCard title="面试轮次" value={roundLabel(dominantRound)} icon={<Users className="h-3.5 w-3.5" />} />
                            <MetricCard title="已评题数" value={questionProgress} icon={<BarChart3 className="h-3.5 w-3.5" />} />
                            <MetricCard title="会话时长" value={formatDuration(report.summary.duration_seconds)} icon={<Clock3 className="h-3.5 w-3.5" />} />
                        </div>

                        <div className="mt-5 rounded-2xl border border-[#E5E5E5] bg-white p-4">
                            <div className="flex items-center justify-between gap-2">
                                <p className="text-sm font-medium text-[#111111]">风险热度条</p>
                                <span className="text-sm text-[#666666]">{formatNum(riskHeatValue)}%</span>
                            </div>
                            <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-[#ECE9E1]">
                                <div
                                    className="h-full rounded-full transition-[width,background] duration-500 ease-out"
                                    style={riskHeatFillStyle}
                                />
                            </div>
                        </div>
                    </section>

                    <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                        <div className="flex items-center gap-2">
                            <TrendingUp className="h-5 w-5 text-[#556987]" />
                            <h2 className="text-xl text-[#111111]">轮次稳定性与校准</h2>
                        </div>

                        {roundProfiles.length > 0 ? (
                            <>
                                <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(300px,0.9fr)]">
                                    <div className="space-y-4">
                                        <div className="grid gap-3 sm:grid-cols-2">
                                            <InsightMetric
                                                title="轮次数"
                                                value={String(interviewStability?.round_count || roundSummary?.total_rounds || roundProfiles.length)}
                                                icon={<Users className="h-4 w-4" />}
                                            />
                                            <InsightMetric
                                                title="平均稳定度"
                                                value={formatNum(interviewStability?.avg_consistency_score)}
                                                icon={<Target className="h-4 w-4" />}
                                            />
                                        </div>

                                        <div className="grid gap-3 xl:grid-cols-1">
                                            {roundProfiles.map((item) => (
                                                <div key={`round-profile-${item.round_type}`} className="rounded-2xl border border-[#E5E5E5] bg-[#FCFBF8] p-4">
                                                    <div className="flex flex-wrap items-start justify-between gap-2">
                                                        <div>
                                                            <p className="text-sm font-medium text-[#111111]">{roundLabel(item.round_type)}</p>
                                                            <p className="mt-1 text-xs text-[#888888]">
                                                                使用 {item.turn_count_used} 题 · 排除 {item.turn_count_excluded} 题 · 总计 {item.turn_count_total} 题
                                                            </p>
                                                        </div>
                                                        <span className={`rounded-full px-2.5 py-1 text-xs ${relativeBandTone(item.relative_band)}`}>
                                                            {relativeBandLabel(item.relative_band, item.relative_position, item.baseline_sample_size)}
                                                        </span>
                                                    </div>

                                                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                                                        <div className="rounded-xl border border-[#E5E5E5] bg-white p-3">
                                                            <p className="text-xs text-[#777777]">轮次原始分</p>
                                                            <p className="mt-1 text-lg font-semibold text-[#111111]">{formatNum(item.round_score_raw)}</p>
                                                        </div>
                                                        <div className="rounded-xl border border-[#E5E5E5] bg-white p-3">
                                                            <p className="text-xs text-[#777777]">轮次稳定分</p>
                                                            <p className="mt-1 text-lg font-semibold text-[#111111]">{formatNum(item.round_score_stable)}</p>
                                                        </div>
                                                        <div className="rounded-xl border border-[#E5E5E5] bg-white p-3">
                                                            <p className="text-xs text-[#777777]">稳定度</p>
                                                            <p className="mt-1 text-lg font-semibold text-[#111111]">{formatNum(item.round_consistency_score)}</p>
                                                        </div>
                                                        <div className="rounded-xl border border-[#E5E5E5] bg-white p-3">
                                                            <p className="text-xs text-[#777777]">基线样本</p>
                                                            <p className="mt-1 text-lg font-semibold text-[#111111]">{item.baseline_sample_size || 0}</p>
                                                        </div>
                                                    </div>

                                                    <div className="mt-3 grid gap-2 sm:grid-cols-3">
                                                        <div className="rounded-xl border border-[#E5E5E5] bg-white px-3 py-2">
                                                            <p className="text-xs text-[#888888]">内容轴</p>
                                                            <p className="mt-1 text-sm font-medium text-[#111111]">{formatNum(item.round_content_score)}</p>
                                                        </div>
                                                        <div className="rounded-xl border border-[#E5E5E5] bg-white px-3 py-2">
                                                            <p className="text-xs text-[#888888]">表达轴</p>
                                                            <p className="mt-1 text-sm font-medium text-[#111111]">{formatNum(item.round_delivery_score)}</p>
                                                        </div>
                                                        <div className="rounded-xl border border-[#E5E5E5] bg-white px-3 py-2">
                                                            <p className="text-xs text-[#888888]">镜头轴</p>
                                                            <p className="mt-1 text-sm font-medium text-[#111111]">{formatNum(item.round_presence_score)}</p>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    <aside className="rounded-2xl border border-[#E5E5E5] bg-[#FAF9F6] p-4 shadow-sm">
                                        <div className="flex items-center gap-2">
                                            <Gauge className="h-4 w-4 text-[#556987]" />
                                            <p className="text-sm font-medium text-[#111111]">稳定性解读</p>
                                        </div>
                                        <p className="mt-3 text-sm leading-6 text-[#666666]">{stabilitySummaryText}</p>

                                        <div className="mt-4 space-y-3">
                                            <div className="rounded-xl border border-[#E5E5E5] bg-white p-3">
                                                <p className="text-xs text-[#888888]">当前主轮次</p>
                                                <p className="mt-1 text-base font-semibold text-[#111111]">
                                                    {primaryRoundProfile ? roundLabel(primaryRoundProfile.round_type) : '--'}
                                                </p>
                                            </div>
                                            <div className="rounded-xl border border-[#E5E5E5] bg-white p-3">
                                                <p className="text-xs text-[#888888]">相对基线</p>
                                                <p className="mt-1 text-sm font-medium text-[#111111]">
                                                    {primaryRoundProfile
                                                        ? relativeBandLabel(
                                                            primaryRoundProfile.relative_band,
                                                            primaryRoundProfile.relative_position,
                                                            primaryRoundProfile.baseline_sample_size,
                                                        )
                                                        : '暂无可用校准结果'}
                                                </p>
                                            </div>
                                            <div className="rounded-xl border border-[#E5E5E5] bg-white p-3">
                                                <p className="text-xs text-[#888888]">优先关注</p>
                                                <p className="mt-1 text-sm font-medium text-[#111111]">
                                                    {primaryRoundWeakestAxis
                                                        ? `${primaryRoundWeakestAxis.label} ${formatNum(primaryRoundWeakestAxis.score)}`
                                                        : '当前样本不足以识别弱项'}
                                                </p>
                                            </div>
                                        </div>

                                        <div className="mt-4 rounded-xl border border-dashed border-[#D8D4CA] bg-white/80 p-3">
                                            <p className="text-xs text-[#777777]">阅读建议</p>
                                            <p className="mt-1 text-xs leading-5 text-[#666666]">
                                                先看“轮次稳定分”判断本轮真实发挥，再结合三轴分数定位是内容组织、表达呈现还是镜头状态更值得优先优化。
                                            </p>
                                        </div>
                                    </aside>
                                </div>
                            </>
                        ) : (
                            <div className="mt-4 rounded-2xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] p-4 text-sm text-[#666666]">
                                暂无可用的轮次聚合数据，当前报告仍按单题结构化结果展示。
                            </div>
                        )}
                    </section>

                    <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                        <div className="flex items-center gap-2">
                            <Gauge className="h-5 w-5 text-[#556987]" />
                            <h2 className="text-xl text-[#111111]">评分可信度拆解</h2>
                        </div>
                        <p className="mt-2 text-sm text-[#666666]">
                            用于解释当前分数的“可信程度”来自哪里，区分样本不足、模型不稳和证据支持不充分这三类原因。
                        </p>

                        {hasConfidenceBreakdown ? (
                            <>
                                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                                    <InsightMetric
                                        title="内容轴可信度"
                                        value={formatConfidencePercent(contentConfidence?.overall_confidence)}
                                        icon={<Target className="h-4 w-4" />}
                                    />
                                    <InsightMetric
                                        title="表达轴可信度"
                                        value={formatConfidencePercent(deliveryConfidence?.overall_confidence)}
                                        icon={<Mic className="h-4 w-4" />}
                                    />
                                    <InsightMetric
                                        title="镜头轴可信度"
                                        value={formatConfidencePercent(presenceConfidence?.overall_confidence)}
                                        icon={<Camera className="h-4 w-4" />}
                                    />
                                    <InsightMetric
                                        title="融合可信度"
                                        value={formatConfidencePercent(evaluationV2?.fusion?.overall_confidence)}
                                        icon={<ShieldCheck className="h-4 w-4" />}
                                    />
                                </div>

                                <div className="mt-4 grid gap-3 xl:grid-cols-3">
                                    {Object.entries(confidenceAxes).map(([axisKey, breakdown]) => (
                                        <div key={`confidence-${axisKey}`} className="rounded-2xl border border-[#E5E5E5] bg-[#FCFBF8] p-4">
                                            <div className="flex items-start justify-between gap-2">
                                                <div>
                                                    <p className="text-sm font-medium text-[#111111]">{confidenceAxisLabel(axisKey)}</p>
                                                    <p className="mt-1 text-xs leading-5 text-[#777777]">{confidenceAxisDescription(axisKey)}</p>
                                                </div>
                                                <span className={`rounded-full px-2.5 py-1 text-xs ${confidenceTone(breakdown?.overall_confidence)}`}>
                                                    总体 {formatConfidencePercent(breakdown?.overall_confidence)}
                                                </span>
                                            </div>

                                            <div className="mt-3 grid grid-cols-2 gap-2">
                                                <div className="rounded-xl border border-[#E5E5E5] bg-white p-3">
                                                    <p className="text-xs text-[#777777]">数据可信度</p>
                                                    <p className="mt-1 text-sm font-medium text-[#111111]">{formatConfidencePercent(breakdown?.data_confidence)}</p>
                                                </div>
                                                <div className="rounded-xl border border-[#E5E5E5] bg-white p-3">
                                                    <p className="text-xs text-[#777777]">模型可信度</p>
                                                    <p className="mt-1 text-sm font-medium text-[#111111]">{formatConfidencePercent(breakdown?.model_confidence)}</p>
                                                </div>
                                                <div className="rounded-xl border border-[#E5E5E5] bg-white p-3">
                                                    <p className="text-xs text-[#777777]">证据/规则可信度</p>
                                                    <p className="mt-1 text-sm font-medium text-[#111111]">{formatConfidencePercent(breakdown?.rubric_confidence)}</p>
                                                </div>
                                                <div className="rounded-xl border border-[#E5E5E5] bg-white p-3">
                                                    <p className="text-xs text-[#777777]">样本数</p>
                                                    <p className="mt-1 text-sm font-medium text-[#111111]">{String(breakdown?.sample_size || 0)}</p>
                                                </div>
                                            </div>

                                            <p className="mt-3 text-xs leading-5 text-[#888888]">
                                                {Number(breakdown?.sample_size || 0) > 0
                                                    ? '分数越高，说明这一轴当前结果越建立在足够样本、稳定模型链路和充分证据支撑之上。'
                                                    : '样本不足，当前不对这一轴给出稳定可信度判断。'}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </>
                        ) : (
                            <div className="mt-4 rounded-2xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] p-4 text-sm text-[#666666]">
                                当前报告还没有可用的可信度拆解数据，通常是因为这场面试尚未完成结构化评分，或历史记录生成时尚未接入该能力。
                            </div>
                        )}
                    </section>

                    <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                        <div className="flex items-center gap-2">
                            <Target className="h-5 w-5 text-[#556987]" />
                            <h2 className="text-xl text-[#111111]">能力雷达（弱项优先）</h2>
                        </div>
                        <p className="mt-2 text-sm text-[#666666]">雷达图用于快速定位本场优先改进维度。</p>
                        <div className="mt-4">
                            <RadarSnapshot dimensions={radarDimensions} />
                        </div>
                    </section>

                    <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                        <div className="flex items-center gap-2">
                            <MessageSquare className="h-5 w-5 text-[#556987]" />
                            <h2 className="text-xl text-[#111111]">内容表现与可追溯依据</h2>
                        </div>
                        <p className="mt-2 text-sm text-[#666666]">{contentPerf?.status_message || '暂无内容表现依据。'}</p>

                        {contentPerf?.status === 'ready' ? (
                            <>
                                <div className="mt-4 grid gap-3 md:grid-cols-2">
                                    {(contentPerf.weak_dimensions || []).slice(0, 4).map((dim) => (
                                        <div key={dim.key} className="rounded-xl border border-[#E5E5E5] p-3">
                                            <div className="flex items-center justify-between gap-2">
                                                <p className="text-sm font-medium text-[#111111]">{dim.label}</p>
                                                <span className="rounded-full bg-[#F3EFE4] px-2 py-1 text-xs text-[#6A5A2B]">
                                                    均分 {formatNum(dim.avg_score)}
                                                </span>
                                            </div>
                                            <p className="mt-1 text-xs text-[#777777]">样本 {dim.sample_count}</p>
                                            {(dim.reason_tags || []).length > 0 && (
                                                <div className="mt-2 flex flex-wrap gap-1.5">
                                                    {(dim.reason_tags || []).map((tag) => (
                                                        <span key={`${dim.key}-${tag}`} className={`rounded-full px-2 py-0.5 text-xs ${reasonTagTone(tag)}`}>
                                                            {tag}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}
                                            {(dim.reasons || []).slice(0, 1).map((reason, index) => (
                                                <p key={`${dim.key}-${index}`} className="mt-2 text-sm text-[#555555]">依据：{reason}</p>
                                            ))}
                                        </div>
                                    ))}
                                </div>

                                <div className="mt-5 rounded-2xl border border-[#E5E5E5] bg-[#FCFBF8] p-4">
                                    <div className="flex items-center gap-2">
                                        <BarChart3 className="h-4 w-4 text-[#556987]" />
                                        <p className="text-sm font-medium text-[#111111]">证据时间轴</p>
                                    </div>
                                    <div className="mt-3 hidden">
                                        {(contentPerf.question_evidence || []).slice(0, 6).map((item, index, arr) => (
                                            <div key={`${item.turn_id}-${item.round_type}`} className="relative pb-4 pl-9">
                                                {index < arr.length - 1 && (
                                                    <span className="absolute left-[13px] top-7 h-[calc(100%-8px)] w-px bg-[#DDD7CA]" />
                                                )}
                                                <span className="absolute left-0 top-1.5 flex h-7 w-7 items-center justify-center rounded-full border border-[#D8D2C6] bg-white text-xs text-[#555555]">
                                                    {index + 1}
                                                </span>
                                                <div className="rounded-xl border border-[#E5E5E5] bg-white p-4">
                                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                                        <span className="rounded-full bg-white px-2.5 py-1 text-xs text-[#555555]">{item.round_type || 'unknown'}</span>
                                                        <span className="rounded-full bg-[#FDECEC] px-2.5 py-1 text-xs text-[#8A3B3B]">单题分 {formatNum(item.overall_score)}</span>
                                                    </div>
                                                    <p className="mt-2 text-sm font-medium text-[#111111]">Q：{item.question_excerpt || '暂无题干'}</p>
                                                    <p className="mt-1 text-sm text-[#555555]">A：{item.answer_excerpt || '暂无回答文本'}</p>
                                                    {(item.reason_tags || []).length > 0 && (
                                                        <div className="mt-2 flex flex-wrap gap-1.5">
                                                            {(item.reason_tags || []).map((tag) => (
                                                                <span key={`${item.turn_id}-${tag}`} className={`rounded-full px-2 py-0.5 text-xs ${reasonTagTone(tag)}`}>
                                                                    {tag}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    )}
                                                    <div className="mt-2 flex flex-wrap gap-2">
                                                        {(item.weak_dimensions || []).map((dim) => (
                                                            <span key={`${item.turn_id}-${dim.key}`} className="rounded-full border border-[#E5E5E5] bg-white px-2.5 py-1 text-xs text-[#555555]">
                                                                {dim.label} {formatNum(dim.score)}
                                                            </span>
                                                        ))}
                                                    </div>
                                                    {(item.evidence_tags || []).length > 0 && (
                                                        <div className="mt-2 flex flex-wrap gap-2">
                                                            {(item.evidence_tags || []).map((tag, tagIndex) => (
                                                                <span key={`${item.turn_id}-tag-${tagIndex}`} className="rounded-full bg-[#EFEDE8] px-2 py-1 text-xs text-[#666666]">
                                                                    {tag}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    )}
                                                    <p className="mt-2 text-xs text-[#888888]">来源：{item.trace_source || 'interview_evaluations'}</p>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                    <p className="mt-2 text-xs text-[#888888]">按题目切换查看证据摘要，下面的单题表现解读会同步联动。</p>
                                    <div className="mt-3 flex flex-wrap gap-2">
                                        {(contentPerf.question_evidence || []).slice(0, 8).map((item, index) => {
                                            const turnId = String(item.turn_id || '').trim()
                                            const active = turnId ? turnId === activeTurnId : activeQuestionIndex === index
                                            const disabled = !turnId && !item.question_excerpt
                                            return (
                                                <button
                                                    key={`evidence-turn-${turnId || index}`}
                                                    type="button"
                                                    disabled={disabled}
                                                    onClick={() => {
                                                        if (disabled) return
                                                        if (turnId) setActiveTurnId(turnId)
                                                    }}
                                                    className={`rounded-full border px-3 py-1 text-xs transition ${active
                                                        ? 'border-[#9AA7BC] bg-[#EAF0F8] text-[#2F4566]'
                                                        : 'border-[#E0DBCF] bg-white text-[#555555] hover:bg-[#F5F2EA]'
                                                        } ${disabled ? 'cursor-not-allowed opacity-50 hover:bg-white' : ''}`}
                                                >
                                                    题目 {index + 1} · {formatNum(item.overall_score)}
                                                </button>
                                            )
                                        })}
                                    </div>
                                    {activeQuestionEvidence ? (
                                        <div className="mt-3 rounded-xl border border-[#E5E5E5] bg-white p-4">
                                            <div className="flex flex-wrap items-center justify-between gap-2">
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <span className="rounded-full bg-[#F7F4EC] px-2.5 py-1 text-xs text-[#555555]">
                                                        当前查看：题目 {activeQuestionIndex >= 0 ? activeQuestionIndex + 1 : 1}
                                                    </span>
                                                    <span className="rounded-full bg-white px-2.5 py-1 text-xs text-[#555555]">
                                                        {activeQuestionEvidence.round_type || 'unknown'}
                                                    </span>
                                                </div>
                                                <span className="rounded-full bg-[#FDECEC] px-2.5 py-1 text-xs text-[#8A3B3B]">
                                                    单题分 {formatNum(activeTurnOverallScore)}
                                                </span>
                                            </div>
                                            <p className="mt-2 text-sm font-medium text-[#111111]">Q：{activeQuestionEvidence.question_excerpt || '暂无题干'}</p>
                                            <p className="mt-1 text-sm text-[#555555]">A：{activeQuestionEvidence.answer_excerpt || '暂无回答文本'}</p>
                                            {activeEvidenceServices.length > 0 ? (
                                                <div className="mt-3 grid gap-3 xl:grid-cols-3">
                                                    {activeEvidenceServices.map((service, index) => {
                                                        const featureEntries = Object.entries(service.features || {}).slice(0, 5)
                                                        const quotes = (service.quotes || []).filter(Boolean).slice(0, 1)
                                                        const signals = (service.signals || []).slice(0, 4)
                                                        const gateReasons = service.quality_gate?.reasons || []
                                                        return (
                                                            <div
                                                                key={`active-evidence-service-${service.source || index}`}
                                                                className="rounded-xl border border-[#E5E5E5] bg-[#FCFBF8] p-3"
                                                            >
                                                                <div className="flex items-start justify-between gap-2">
                                                                    <div>
                                                                        <p className="text-sm font-medium text-[#111111]">
                                                                            {evidenceSourceLabel(service.source)}
                                                                        </p>
                                                                        <p className="mt-1 text-xs text-[#888888]">
                                                                            {service.status === 'ready' ? '证据已就绪' : `状态：${service.status || 'unknown'}`}
                                                                        </p>
                                                                    </div>
                                                                    <span className={`rounded-full px-2.5 py-1 text-xs ${confidenceTone(service.confidence)}`}>
                                                                        可信度 {formatConfidencePercent(service.confidence)}
                                                                    </span>
                                                                </div>
                                                                {service.quality_gate && (
                                                                    <p className="mt-2 text-xs text-[#666666]">
                                                                        质量门控：{service.quality_gate.passed ? '通过' : '未通过'}
                                                                        {gateReasons.length > 0 ? `（${gateReasons.join('、')}）` : ''}
                                                                    </p>
                                                                )}
                                                                {featureEntries.length > 0 && (
                                                                    <div className="mt-2 flex flex-wrap gap-2">
                                                                        {featureEntries.map(([key, value]) => (
                                                                            <span
                                                                                key={`${service.source}-${key}`}
                                                                                className="rounded-full border border-[#E5E5E5] bg-white px-2.5 py-1 text-xs text-[#555555]"
                                                                            >
                                                                                {evidenceFeatureLabel(key)} {formatEvidenceFeatureValue(key, value)}
                                                                            </span>
                                                                        ))}
                                                                    </div>
                                                                )}
                                                                {signals.length > 0 && (
                                                                    <div className="mt-2 flex flex-wrap gap-1.5">
                                                                        {signals.map((signal, signalIndex) => (
                                                                            <span
                                                                                key={`${service.source}-signal-${signalIndex}`}
                                                                                className={`rounded-full px-2 py-0.5 text-xs ${evidenceSeverityTone(signal.severity)}`}
                                                                            >
                                                                                {signal.label || signal.code || 'signal'}
                                                                            </span>
                                                                        ))}
                                                                    </div>
                                                                )}
                                                                {quotes.length > 0 && (
                                                                    <p className="mt-2 text-xs leading-5 text-[#666666]">
                                                                        摘录：{quotes[0]}
                                                                    </p>
                                                                )}
                                                            </div>
                                                        )
                                                    })}
                                                </div>
                                            ) : (
                                                <>
                                                    {(activeQuestionEvidence.reason_tags || []).length > 0 && (
                                                        <div className="mt-2 flex flex-wrap gap-1.5">
                                                            {(activeQuestionEvidence.reason_tags || []).map((tag) => (
                                                                <span key={`active-evidence-tag-${tag}`} className={`rounded-full px-2 py-0.5 text-xs ${reasonTagTone(tag)}`}>
                                                                    {tag}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    )}
                                                    <div className="mt-2 flex flex-wrap gap-2">
                                                        {(activeQuestionEvidence.weak_dimensions || []).map((dim) => (
                                                            <span key={`active-weak-${dim.key}`} className="rounded-full border border-[#E5E5E5] bg-white px-2.5 py-1 text-xs text-[#555555]">
                                                                {dim.label} {formatNum(dim.score)}
                                                            </span>
                                                        ))}
                                                    </div>
                                                    {(activeQuestionEvidence.evidence_tags || []).length > 0 && (
                                                        <div className="mt-2 flex flex-wrap gap-2">
                                                            {(activeQuestionEvidence.evidence_tags || []).map((tag, tagIndex) => (
                                                                <span key={`active-evidence-summary-tag-${tagIndex}`} className="rounded-full bg-[#EFEDE8] px-2 py-1 text-xs text-[#666666]">
                                                                    {tag}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    )}
                                                    <p className="mt-2 text-xs text-[#888888]">来源：{activeQuestionEvidence.trace_source || 'interview_evaluations'}</p>
                                                </>
                                            )}
                                        </div>
                                    ) : (
                                        <p className="mt-3 rounded-xl border border-dashed border-[#D8D4CA] bg-white p-4 text-sm text-[#666666]">
                                            当前没有可展示的单题证据摘要。
                                        </p>
                                    )}
                                </div>

                                <div className="mt-5 rounded-2xl border border-[#E5E5E5] bg-[#FCFBF8] p-4">
                                    <div className="flex items-center justify-between gap-2">
                                        <div className="flex items-center gap-2">
                                            <ShieldCheck className="h-4 w-4 text-[#556987]" />
                                            <p className="text-sm font-medium text-[#111111]">单题表现解读</p>
                                        </div>
                                        {!!activeTurnId && (
                                            <button
                                                type="button"
                                                onClick={refreshActiveTurnAudit}
                                                className="rounded-lg border border-[#E5E5E5] bg-white px-2.5 py-1 text-xs text-[#555555] hover:bg-[#F5F2EA]"
                                            >
                                                刷新本题
                                            </button>
                                        )}
                                    </div>
                                    <p className="mt-2 text-xs text-[#888888]">选择题目后，可查看“为什么扣分”以及“下一步怎么改”。</p>

                                    <div className="mt-3 hidden flex flex-wrap gap-2">
                                        {(contentPerf.question_evidence || []).slice(0, 6).map((item, index) => {
                                            const turnId = String(item.turn_id || '').trim()
                                            const active = turnId === activeTurnId
                                            const disabled = !turnId
                                            return (
                                                <button
                                                    key={`audit-turn-${turnId || index}`}
                                                    type="button"
                                                    disabled={disabled}
                                                    onClick={() => {
                                                        if (disabled) return
                                                        if (active) {
                                                            refreshActiveTurnAudit()
                                                            return
                                                        }
                                                        setActiveTurnId(turnId)
                                                    }}
                                                    className={`rounded-full border px-3 py-1 text-xs transition ${active
                                                        ? 'border-[#9AA7BC] bg-[#EAF0F8] text-[#2F4566]'
                                                        : 'border-[#E0DBCF] bg-white text-[#555555] hover:bg-[#F5F2EA]'
                                                        } ${disabled ? 'cursor-not-allowed opacity-50 hover:bg-white' : ''}`}
                                                >
                                                    题目 {index + 1} · {formatNum(item.overall_score)}{disabled ? '（缺少 turn_id）' : ''}
                                                </button>
                                            )
                                        })}
                                    </div>

                                    {scorecardLoading ? (
                                        <p className="mt-3 rounded-xl border border-dashed border-[#D8D4CA] bg-white p-4 text-sm text-[#666666]">单题证据链加载中...</p>
                                    ) : scorecardError ? (
                                        <div className="mt-3 rounded-xl border border-[#F0D7D2] bg-[#FFF6F4] p-4 text-sm text-[#8A3B3B]">
                                            <p>{scorecardError}</p>
                                            {!!activeTurnId && (
                                                <button
                                                    type="button"
                                                    onClick={refreshActiveTurnAudit}
                                                    className="mt-2 rounded-lg border border-[#E5B8B1] bg-white px-3 py-1 text-xs text-[#8A3B3B] hover:bg-[#FFF0ED]"
                                                >
                                                    重试获取证据链
                                                </button>
                                            )}
                                        </div>
                                    ) : activeScorecard?.evaluation ? (
                                        <>
                                            <div className="mt-3 rounded-xl border border-[#E5E5E5] bg-white p-4">
                                                <p className="text-sm font-medium text-[#111111]">本题结论</p>
                                                <p className="mt-2 text-sm text-[#555555]">{activeQuestionEvidence?.question_excerpt || '暂无题干信息'}</p>

                                                <div className="mt-3 grid gap-2 sm:grid-cols-3">
                                                    <div className="rounded-lg border border-[#EEE9DD] bg-[#FAF8F2] px-3 py-2">
                                                        <p className="text-xs text-[#777777]">本题得分</p>
                                                        <p className="mt-1 text-base font-semibold text-[#111111]">
                                                            {formatNum(activeTurnOverallScore)}
                                                        </p>
                                                    </div>
                                                    <div className="rounded-lg border border-[#EEE9DD] bg-[#FAF8F2] px-3 py-2">
                                                        <p className="text-xs text-[#777777]">优先改进维度</p>
                                                        <p className="mt-1 text-base font-semibold text-[#111111]">{weakestDimensionLabel}</p>
                                                    </div>
                                                    <div className="rounded-lg border border-[#EEE9DD] bg-[#FAF8F2] px-3 py-2">
                                                        <p className="text-xs text-[#777777]">改进建议</p>
                                                        <p className="mt-1 text-xs leading-5 text-[#444444]">{primaryImprovementAdvice}</p>
                                                    </div>
                                                </div>

                                                {(activeQuestionEvidence?.reason_tags || []).length > 0 && (
                                                    <div className="mt-3 flex flex-wrap gap-1.5">
                                                        {(activeQuestionEvidence?.reason_tags || []).map((tag) => (
                                                            <span key={`active-reason-tag-${tag}`} className={`rounded-full px-2 py-0.5 text-xs ${reasonTagTone(tag)}`}>
                                                                {tag}
                                                            </span>
                                                        ))}
                                                    </div>
                                                )}

                                                {!!activeQuestionEvidence?.answer_excerpt && (
                                                    <div className="mt-3 rounded-lg border border-[#EDEBE4] bg-[#FBFBF9] p-3">
                                                        <p className="text-xs text-[#888888]">回答摘录</p>
                                                        <p className="mt-1 text-sm text-[#555555]">{activeQuestionEvidence.answer_excerpt}</p>
                                                    </div>
                                                )}

                                                {activeQuestionSummary.length > 0 && (
                                                    <div className="mt-3 rounded-lg border border-[#EDEBE4] bg-[#FCFBF8] p-3">
                                                        <p className="text-xs text-[#888888]">本题总评</p>
                                                        <div className="mt-1 space-y-1.5 text-sm leading-6 text-[#555555]">
                                                            {activeQuestionSummary.map((line, index) => (
                                                                <p key={`active-summary-${index}`}>{line}</p>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>

                                            {readableDimensionCards.length > 0 ? (
                                                <div className="mt-3 grid gap-3 md:grid-cols-2">
                                                    {readableDimensionCards.map((dimValue) => (
                                                        <div key={`dim-evidence-${dimValue.key}`} className="rounded-xl border border-[#E5E5E5] bg-white p-3">
                                                            <div className="flex items-center justify-between gap-2">
                                                                <p className="text-sm font-medium text-[#111111]">{dimValue.label}</p>
                                                                <span className="rounded-full bg-[#F1EEE7] px-2 py-1 text-xs text-[#555555]">{formatNum(dimValue.score)}</span>
                                                            </div>
                                                            <progress
                                                                className="mt-2 h-2 w-full overflow-hidden rounded-full [appearance:none] [&::-webkit-progress-bar]:bg-[#ECE9E1] [&::-webkit-progress-value]:bg-[#4C6A8A] [&::-moz-progress-bar]:bg-[#4C6A8A]"
                                                                value={dimValue.scoreValue}
                                                                max={100}
                                                            />
                                                            <div className="mt-2 space-y-1.5 text-xs leading-6 text-[#555555]">
                                                                <p>{dimValue.overview}</p>
                                                                <p className="text-[#3E7657]">{dimValue.highlightText}</p>
                                                                <p className="text-[#8A3B3B]">{dimValue.gapText}</p>
                                                                <p className="text-[#666666]">{dimValue.evidenceText}</p>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            ) : (
                                                <p className="mt-3 rounded-xl border border-dashed border-[#D8D4CA] bg-white p-4 text-sm text-[#666666]">当前题目暂无维度级解释数据。</p>
                                            )}
                                        </>
                                    ) : (
                                        <p className="mt-3 rounded-xl border border-dashed border-[#D8D4CA] bg-white p-4 text-sm text-[#666666]">当前单题暂无可展示的证据链数据。</p>
                                    )}
                                </div>
                            </>
                        ) : (
                            <p className="mt-4 rounded-xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] p-4 text-sm text-[#666666]">内容表现证据暂不可用。</p>
                        )}
                    </section>

                    <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                        <div className="flex items-center gap-2">
                            <Mic className="h-5 w-5 text-[#556987]" />
                            <h2 className="text-xl text-[#111111]">语音表达分析</h2>
                        </div>
                        <p className="mt-2 text-sm text-[#666666]">{speechPerf?.status_message || '暂无语音分析。'}</p>

                        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                            <InsightMetric title="平均语速" value={`${formatNum(speechPerf?.summary?.avg_speech_rate_wpm)} 词/分钟`} icon={<Gauge className="h-4 w-4" />} />
                            <InsightMetric title="口头词/百词" value={formatNum(speechPerf?.summary?.avg_fillers_per_100_words, 2)} icon={<Volume2 className="h-4 w-4" />} />
                            <InsightMetric title="停顿异常比" value={`${formatNum(Number(speechPerf?.summary?.avg_pause_anomaly_ratio || 0) * 100)}%`} icon={<BarChart3 className="h-4 w-4" />} />
                            <InsightMetric title="语音样本数" value={String(speechPerf?.summary?.samples || 0)} icon={<Mic className="h-4 w-4" />} />
                        </div>

                        {speechRadarDimensions.length > 0 && (
                            <div className="mt-4 grid gap-4 xl:grid-cols-[1.15fr,0.85fr]">
                                <RadarSnapshot dimensions={speechRadarDimensions} title="语音能力雷达" />
                                <div className="rounded-2xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
                                    <p className="text-sm font-medium text-[#111111]">优先改进项（语音）</p>
                                    <p className="mt-1 text-xs text-[#888888]">按得分从低到高排序，建议优先提升前两项。</p>
                                    <div className="mt-3 space-y-2">
                                        {speechWeakItems.map((item, index) => (
                                            <div key={`speech-weak-${item.key}`} className="rounded-xl border border-[#E5E5E5] bg-white px-3 py-2">
                                                <div className="flex items-center justify-between gap-2">
                                                    <p className="text-sm text-[#111111]">{index + 1}. {item.label}</p>
                                                    <span className="rounded-full bg-[#FDECEC] px-2 py-0.5 text-xs text-[#8A3B3B]">{formatNum(item.score)}</span>
                                                </div>
                                                <p className="mt-1 text-xs text-[#666666]">
                                                    {item.score < 60 ? '较弱：建议优先训练，重点改善表达稳定性。' : item.score < 75 ? '偏弱：建议通过模拟问答提升这一项。' : '可继续保持，重点巩固稳定输出。'}
                                                </p>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}

                        {(speechPerf?.diagnosis || []).length > 0 && (
                            <div className="mt-4 rounded-xl border border-[#E5E5E5] bg-[#F8F7F3] p-4 text-sm text-[#555555]">
                                {(speechPerf?.diagnosis || []).map((item, index) => (
                                    <p key={`diag-${index}`} className={index === 0 ? '' : 'mt-1'}>{item}</p>
                                ))}
                            </div>
                        )}

                        {(speechPerf?.evidence_samples || []).length > 0 && (
                            <div className="mt-4 space-y-3">
                                {(speechPerf?.evidence_samples || []).slice(0, 4).map((sample) => (
                                    <div key={sample.turn_id || sample.transcript_excerpt} className="rounded-xl border border-[#E5E5E5] p-3">
                                        <p className="text-sm text-[#111111]">文本样本：{sample.transcript_excerpt || '暂无转写文本'}</p>
                                        <div className="mt-2 flex flex-wrap gap-2 text-xs text-[#666666]">
                                            <span className="rounded-full bg-[#F0EEEA] px-2 py-1">语速 {formatNum(sample.speech_rate_wpm)} 词/分钟</span>
                                            <span className="rounded-full bg-[#F0EEEA] px-2 py-1">口头词 {formatNum(sample.fillers_per_100_words, 2)}/百词</span>
                                            <span className="rounded-full bg-[#F0EEEA] px-2 py-1">长停顿 {sample.long_pause_count}</span>
                                            <span className="rounded-full bg-[#F0EEEA] px-2 py-1">停顿异常比 {formatNum(Number(sample.pause_anomaly_ratio || 0) * 100)}%</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </section>

                    <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                        <div className="flex items-center gap-2">
                            <Camera className="h-5 w-5 text-[#556987]" />
                            <h2 className="text-xl text-[#111111]">镜头前表现</h2>
                        </div>
                        <p className="mt-2 text-sm text-[#666666]">{cameraPerf?.status_message || '基于防作弊事件与统计指标生成。'}</p>

                        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                            <InsightMetric title="镜头稳定分" value={formatNum(cameraPerf?.focus_score)} icon={<Eye className="h-4 w-4" />} />
                            <InsightMetric title="规范性分" value={formatNum(cameraPerf?.compliance_score)} icon={<Users className="h-4 w-4" />} />
                            <InsightMetric title="屏幕外注视" value={`${formatNum(cameraStats?.off_screen_ratio)}%`} icon={<TrendingUp className="h-4 w-4" />} />
                            <InsightMetric title="多人同框次数" value={String(cameraStats?.total_multi_person || 0)} icon={<Users className="h-4 w-4" />} />
                        </div>

                        {(cameraInsights && Number(cameraInsights.sample_count || 0) > 0) && (
                            <div className="mt-4 space-y-4">
                                <div className="grid gap-3 lg:grid-cols-2">
                                    <div className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
                                        <p className="text-sm font-medium text-[#111111]">1. 478 个 三维人脸关键点</p>
                                        <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-[#555555]">
                                            <DataPill label="平均关键点数" value={formatNum(cameraLandmarks?.avg_landmark_count, 1)} />
                                            <DataPill label="最大关键点数" value={formatNum(cameraLandmarks?.max_landmark_count, 0)} />
                                            <DataPill label="嘴部开合比" value={formatNum(cameraLandmarks?.avg_mouth_open_ratio, 4)} />
                                            <DataPill label="微动方差" value={formatNum(cameraLandmarks?.avg_micro_movement_variance, 6)} />
                                            <DataPill label="距离Z均值" value={formatNum(cameraLandmarks?.avg_face_distance_z, 4)} />
                                            <DataPill label="过近/过远" value={`${formatNum(cameraLandmarks?.close_ratio)}% / ${formatNum(cameraLandmarks?.far_ratio)}%`} />
                                        </div>
                                    </div>

                                    <div className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
                                        <p className="text-sm font-medium text-[#111111]">2. 52 个表情系数</p>
                                        <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-[#555555]">
                                            <DataPill label="跟踪系数数" value={formatNum(cameraBlendshape?.tracked_count_max, 0)} />
                                            <DataPill label="眨眼频率" value={`${formatNum(cameraBlendshape?.avg_blink_rate_per_min, 1)} 次/分钟`} />
                                            <DataPill label="browInnerUp" value={formatNum(cameraBlendshape?.avg_brow_inner_up, 4)} />
                                            <DataPill label="微笑均值" value={formatNum(cameraBlendshape?.avg_smile, 4)} />
                                            <DataPill label="jawOpen" value={formatNum(cameraBlendshape?.avg_jaw_open, 4)} />
                                            <DataPill label="言语表现力" value={formatNum(cameraBlendshape?.avg_speech_expressiveness, 2)} />
                                        </div>
                                    </div>

                                    <div className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
                                        <p className="text-sm font-medium text-[#111111]">3. 头部姿态（俯仰 / 偏航 / 翻滚）</p>
                                        <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-[#555555]">
                                            <DataPill label="平均 |Pitch|" value={`${formatNum(cameraHeadPose?.avg_abs_pitch, 2)}°`} />
                                            <DataPill label="平均 |Yaw|" value={`${formatNum(cameraHeadPose?.avg_abs_yaw, 2)}°`} />
                                            <DataPill label="平均 |Roll|" value={`${formatNum(cameraHeadPose?.avg_abs_roll, 2)}°`} />
                                            <DataPill label="姿态异常帧占比" value={`${formatNum(cameraHeadPose?.high_pose_ratio, 2)}%`} />
                                        </div>
                                    </div>

                                    <div className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
                                        <p className="text-sm font-medium text-[#111111]">4. 虹膜追踪</p>
                                        <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-[#555555]">
                                            <DataPill label="平均注视偏移" value={formatNum(cameraIris?.avg_gaze_offset_magnitude, 4)} />
                                            <DataPill label="平均聚焦分" value={formatNum(cameraIris?.avg_gaze_focus_score, 2)} />
                                            <DataPill label="最大漂移计数" value={formatNum(cameraIris?.max_drift_count, 0)} />
                                            <DataPill label="漂移跃迁次数" value={formatNum(cameraIris?.drift_jumps, 0)} />
                                        </div>
                                    </div>
                                </div>

                                {topBlendshapeAverages.length > 0 && (
                                    <div className="rounded-xl border border-[#E5E5E5] bg-[#F8F7F3] p-4">
                                        <p className="text-sm font-medium text-[#111111]">表情系数活跃度 前 8 项（柱状）</p>
                                        <div className="mt-3 space-y-2">
                                            {topBlendshapeAverages.map(([name, value]) => (
                                                <div key={name} className="grid grid-cols-[120px,1fr,52px] items-center gap-2 text-xs">
                                                    <span className="truncate text-[#666666]">{name}</span>
                                                    <progress
                                                        className="h-2 w-full overflow-hidden rounded-full [appearance:none] [&::-webkit-progress-bar]:bg-[#ECE9E1] [&::-webkit-progress-value]:bg-[#4C6A8A] [&::-moz-progress-bar]:bg-[#4C6A8A]"
                                                        value={Math.max(0, Math.min(1, Number(value || 0)))}
                                                        max={1}
                                                    />
                                                    <span className="text-right text-[#555555]">{formatNum(value, 4)}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {(cameraPerf?.notes || []).length > 0 && (
                            <div className="mt-4 rounded-xl border border-[#E5E5E5] bg-[#F8F7F3] p-4 text-sm text-[#555555]">
                                {(cameraPerf?.notes || []).map((note, index) => (
                                    <p key={`camera-note-${index}`} className={index === 0 ? '' : 'mt-1'}>{note}</p>
                                ))}
                            </div>
                        )}

                        {cameraBreakdown.length > 0 && (
                            <div className="mt-4 flex flex-wrap gap-2">
                                {cameraBreakdown.map((item) => (
                                    <span key={`${item.event_type}-${item.count}`} className="inline-flex items-center gap-1 rounded-full border border-[#E5E5E5] bg-white px-2.5 py-1 text-xs text-[#555555]">
                                        {eventLabel(item.event_type)} {item.count}
                                    </span>
                                ))}
                            </div>
                        )}

                        {gazeTrendData.length > 1 && (
                            <div className="mt-4 rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                    <p className="text-sm font-medium text-[#111111]">视线专注度曲线（面试全程）</p>
                                    <div className="flex flex-wrap items-center gap-2 text-xs text-[#666666]">
                                        <span className="rounded-full bg-white px-2 py-1">均值 {formatNum(cameraInsights?.gaze_focus_summary?.avg_focus_score, 1)}</span>
                                        <span className="rounded-full bg-white px-2 py-1">低专注占比 {formatNum(cameraInsights?.gaze_focus_summary?.low_focus_ratio, 1)}%</span>
                                        <span className="rounded-full bg-white px-2 py-1">最低值 {formatNum(cameraInsights?.gaze_focus_summary?.min_focus_score, 1)}</span>
                                    </div>
                                </div>
                                <div className="mt-3 h-72 w-full">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={gazeTrendData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                                            <CartesianGrid stroke="#E7E3D8" strokeDasharray="3 3" />
                                            <ReferenceArea y1={0} y2={60} fill="#FCEBE9" fillOpacity={0.35} />
                                            <XAxis dataKey="second" tick={{ fontSize: 11, fill: '#666666' }} tickFormatter={formatSecondsLabel} />
                                            <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#666666' }} />
                                            <Tooltip
                                                formatter={(value: unknown, name: string) => {
                                                    const num = Number(value)
                                                    const normalized = Number.isFinite(num) ? num.toFixed(1) : '--'
                                                    if (name === 'focus') return [`${normalized}`, '专注度']
                                                    if (name === 'offscreen') return [`${normalized}%`, '离屏占比']
                                                    return [`${normalized}%`, '风险热度']
                                                }}
                                                labelFormatter={(label) => `时间 ${formatSecondsLabel(label)}`}
                                                contentStyle={{ borderRadius: 10, borderColor: '#E5E5E5' }}
                                            />
                                            <Line type="monotone" dataKey="focus" name="focus" stroke="#3E7657" strokeWidth={2.2} dot={false} />
                                            <Line type="monotone" dataKey="offscreen" name="offscreen" stroke="#C17C2D" strokeDasharray="4 4" strokeWidth={1.6} dot={false} />
                                            <Line type="monotone" dataKey="risk" name="risk" stroke="#9D3A2E" strokeOpacity={0.65} strokeWidth={1.4} dot={false} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>

                                {gazeTrendValleys.length > 0 && (
                                    <div className="mt-3 rounded-lg border border-[#E5E5E5] bg-white p-3">
                                        <p className="text-xs text-[#777777]">专注度最低时段（优先复盘）</p>
                                        <div className="mt-2 flex flex-wrap gap-2">
                                            {gazeTrendValleys.map((point, idx) => (
                                                <span key={`valley-${idx}`} className="rounded-full bg-[#FDECEC] px-2.5 py-1 text-xs text-[#8A3B3B]">
                                                    {formatSecondsLabel(point.second)} · 专注 {formatNum(point.focus, 1)}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {gazeTrendData.length <= 1 && cameraTopEvents.length > 0 && (
                            <div className="mt-4 rounded-xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] p-4 text-sm text-[#666666]">
                                暂无可绘制的专注度曲线数据，当前仅保留异常事件摘要。建议进行一场新会话以生成完整曲线。
                            </div>
                        )}
                    </section>

                    <section className="rounded-3xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                        <div className="flex flex-wrap gap-3">
                            <Link href={replayUrl} className="inline-flex items-center gap-2 rounded-xl bg-[#111111] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#222222]">
                                进入面试复盘
                                <ArrowRight className="h-4 w-4" />
                            </Link>
                            <Link href="/history" className="inline-flex items-center gap-2 rounded-xl border border-[#E5E5E5] px-4 py-2.5 text-sm font-medium text-[#111111] hover:bg-[#F5F5F5]">
                                返回历史记录
                            </Link>
                        </div>
                    </section>
                </div>
            </main>
        </div>
    )
}

function ReportPageFallback() {
    return (
        <div className="flex min-h-screen">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-4xl px-6 py-8">
                    <section className="rounded-2xl border border-[#E5E5E5] bg-white p-8 text-center shadow-sm">
                        <p className="text-sm text-[#666666]">报告加载中...</p>
                    </section>
                </div>
            </main>
        </div>
    )
}

export default function ReportPage() {
    return (
        <Suspense fallback={<ReportPageFallback />}>
            <ReportPageContent />
        </Suspense>
    )
}

function MetricCard({ title, value, icon }: { title: string; value: string; icon?: ReactNode }) {
    return (
        <div className="rounded-2xl border border-[#E5E5E5] bg-white p-4">
            <p className="text-xs uppercase tracking-[0.12em] text-[#999999]">{title}</p>
            <p className="mt-2 flex items-center gap-1 text-2xl font-semibold text-[#111111]">{value}{icon}</p>
        </div>
    )
}

function InsightMetric({ title, value, icon }: { title: string; value: string; icon?: ReactNode }) {
    return (
        <div className="rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] p-3">
            <p className="text-xs text-[#888888]">{title}</p>
            <p className="mt-2 flex items-center gap-1 text-lg font-semibold text-[#111111]">{value}{icon}</p>
        </div>
    )
}

function DataPill({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-lg border border-[#E5E5E5] bg-white px-2.5 py-1.5">
            <p className="text-[11px] text-[#888888]">{label}</p>
            <p className="mt-0.5 text-xs font-medium text-[#333333]">{value}</p>
        </div>
    )
}

function RadarSnapshot({
    dimensions,
    title = '多维能力雷达',
}: {
    dimensions: Array<{ key: string; label: string; score: number }>
    title?: string
}) {
    const normalized = (dimensions || []).slice(0, 6)
    if (normalized.length < 3) {
        return <p className="rounded-xl border border-dashed border-[#D8D4CA] bg-[#FAF9F6] p-4 text-sm text-[#666666]">维度数据不足，无法绘制雷达图。</p>
    }

    const size = 220
    const center = size / 2
    const radius = 74
    const viewBoxPadding = 34
    const total = normalized.length

    const pointAt = (index: number, ratio: number) => {
        const angle = (-Math.PI / 2) + (Math.PI * 2 * index / total)
        return {
            x: center + radius * ratio * Math.cos(angle),
            y: center + radius * ratio * Math.sin(angle),
        }
    }

    const axisPoints = normalized.map((item, index) => {
        const score = Math.max(0, Math.min(100, Number(item.score || 0)))
        const valuePoint = pointAt(index, score / 100)
        const outerPoint = pointAt(index, 1)
        const labelPoint = pointAt(index, 1.22)
        return {
            ...item,
            score,
            valuePoint,
            outerPoint,
            labelPoint,
        }
    })

    const polygonPoints = axisPoints.map((item) => `${item.valuePoint.x.toFixed(1)},${item.valuePoint.y.toFixed(1)}`).join(' ')
    const levelPolygons = [0.25, 0.5, 0.75, 1].map((ratio) => {
        const points = normalized.map((_, index) => {
            const point = pointAt(index, ratio)
            return `${point.x.toFixed(1)},${point.y.toFixed(1)}`
        }).join(' ')
        return { ratio, points }
    })

    return (
        <div className="rounded-2xl border border-[#E5E5E5] bg-[#FAF9F6] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium text-[#111111]">{title}</p>
                <p className="text-xs text-[#777777]">分值范围 0-100</p>
            </div>

            <div className="mt-4 flex flex-col gap-4 md:flex-row md:items-start">
                <svg
                    viewBox={`${-viewBoxPadding} ${-viewBoxPadding} ${size + viewBoxPadding * 2} ${size + viewBoxPadding * 2}`}
                    className="h-[240px] w-[240px] shrink-0"
                >
                    {levelPolygons.map((item) => (
                        <polygon key={`grid-${item.ratio}`} points={item.points} fill="none" stroke="#DDD7CA" strokeWidth="1" />
                    ))}
                    {axisPoints.map((item) => (
                        <line key={`axis-${item.key}`} x1={center} y1={center} x2={item.outerPoint.x} y2={item.outerPoint.y} stroke="#E6E1D7" strokeWidth="1" />
                    ))}
                    <polygon points={polygonPoints} fill="rgba(76, 106, 138, 0.18)" stroke="#4C6A8A" strokeWidth="2" />
                    {axisPoints.map((item) => (
                        <circle key={`point-${item.key}`} cx={item.valuePoint.x} cy={item.valuePoint.y} r="3" fill="#4C6A8A" />
                    ))}
                    {axisPoints.map((item) => (
                        <text
                            key={`label-${item.key}`}
                            x={item.labelPoint.x}
                            y={item.labelPoint.y}
                            textAnchor={item.labelPoint.x < center - 8 ? 'end' : item.labelPoint.x > center + 8 ? 'start' : 'middle'}
                            dominantBaseline="middle"
                            fontSize="11"
                            fill="#555555"
                        >
                            {item.label.length > 8 ? `${item.label.slice(0, 8)}…` : item.label}
                        </text>
                    ))}
                </svg>

                <div className="grid flex-1 gap-2 sm:grid-cols-2">
                    {axisPoints.map((item) => (
                        <div key={`legend-${item.key}`} className="rounded-xl border border-[#E5E5E5] bg-white px-3 py-2">
                            <p className="text-xs text-[#777777]">{item.label}</p>
                            <p className="mt-1 text-sm font-semibold text-[#111111]">{formatNum(item.score)}</p>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}


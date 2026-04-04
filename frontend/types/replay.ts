export type TimelineTag = {
    id?: number
    turn_id?: string
    tag_type: 'high' | 'low' | 'turning' | 'emotion' | 'posture' | 'gaze' | string
    start_ms: number
    end_ms: number
    reason?: string
    confidence?: number
    evidence?: Record<string, unknown>
}

export type TranscriptAnchor = {
    turn_id: string
    question: string
    answer: string
    question_start_ms: number
    question_end_ms: number
    answer_start_ms: number
    answer_end_ms: number
    latency_ms: number
}

export type DeepAuditItem = {
    turn_id?: string
    question?: string
    type?: string
    finding?: string
    severity?: string
    dimension?: string
    suggestion?: string
    score?: number
    evidence?: Record<string, unknown>
}

export type ShadowAnswerItem = {
    turn_id?: string
    question?: string
    original_answer?: string
    shadow_answer?: string
    why_better?: string
    resume_alignment?: Record<string, unknown>
}

export type VisualMetricsPayload = {
    latency_matrix?: {
        avg_latency_ms?: number
        items?: Array<{ turn_id?: string; latency_ms?: number }>
    }
    keyword_coverage?: {
        avg_coverage_ratio?: number
        items?: Array<{ turn_id?: string; coverage_ratio?: number }>
    }
    speech_tone?: {
        dimensions?: Record<string, number>
    } & Record<string, unknown>
    radar?: Array<{ key: string; score: number }>
    heatmap?: Array<{ turn_id?: string; latency_ms?: number; coverage_ratio?: number }>
}

export type ReplayPayload = {
    success: boolean
    interview_id: string
    video?: {
        available: boolean
        play_url?: string
        duration_ms?: number
        status?: string
        codec?: string
    }
    transcript_anchor_list: TranscriptAnchor[]
    tags: TimelineTag[]
    audits?: {
        fact_checks?: DeepAuditItem[]
        dimension_gaps?: DeepAuditItem[]
        round_diagnosis?: Record<string, unknown>
    }
    shadow_answers?: ShadowAnswerItem[]
    visual_metrics?: VisualMetricsPayload
    error?: string
}

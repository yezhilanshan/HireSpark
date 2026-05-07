export type GraphNode = {
    id: string
    label: string
    type: string
    group: string
    status?: string | null
    score?: number | null
    description?: string
    meta?: Record<string, unknown>
}

export type GraphEdge = {
    id: string
    source: string
    target: string
    label?: string
    type?: string
}

export type RecentInterview = {
    interview_id: string
    round_type: string
    score?: number | null
    time?: string
    risk_level?: string
}

export type GraphSummary = {
    user_name?: string
    target_position?: string
    capability_count?: number
    strength_count?: number
    risk_count?: number
    active_task_count?: number
    interviews_analyzed?: number
    last_interview_at?: string
    top_strengths?: GraphNode[]
    top_risks?: GraphNode[]
    recent_interviews?: RecentInterview[]
}

export type GraphPayload = {
    success: boolean
    summary: GraphSummary
    nodes: GraphNode[]
    edges: GraphEdge[]
    error?: string
}

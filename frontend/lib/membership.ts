export type MembershipMode = 'personal' | 'team'
export type BillingPlan = 'single' | 'monthly' | 'yearly'

export type MembershipPlan = {
    id: BillingPlan
    title: string
    description: string
    unit_label: string
    base_price: number
    detail: string
    highlight?: string
    quota_total?: number
    duration_days?: number | null
}

export type MembershipCatalog = {
    team_discount: number
    modes: Array<{
        id: MembershipMode
        label: string
        min_team_size: number
    }>
    plans: MembershipPlan[]
}

export type MembershipUsage = {
    total: number
    used: number
    remaining: number
}

export type CurrentMembership = {
    status: 'inactive' | 'active'
    mode: MembershipMode
    plan_id: BillingPlan | null
    plan_title: string | null
    team_size: number
    auto_renew: boolean
    started_at: string | null
    expires_at: string | null
    usage: MembershipUsage
}

export type MembershipOrder = {
    order_id: string
    membership_mode: MembershipMode
    plan_id: BillingPlan
    plan_title: string | null
    team_size: number
    unit_price: number
    total_price: number
    status: 'pending' | 'paid'
    quota_total: number
    quota_used: number
    created_at: string | null
    updated_at: string | null
}

export type MembershipOverviewResponse = {
    success: boolean
    catalog: MembershipCatalog
    current_membership: CurrentMembership
    recent_orders: MembershipOrder[]
    error?: string
}

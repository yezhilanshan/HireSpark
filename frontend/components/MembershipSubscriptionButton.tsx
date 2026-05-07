'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { CheckCircle2, Crown, Loader2, Minus, Plus, Sparkles, Users, X } from 'lucide-react'
import type {
    BillingPlan,
    CurrentMembership,
    MembershipCatalog,
    MembershipMode,
    MembershipOverviewResponse,
    MembershipPlan,
} from '@/lib/membership'
import { cn } from '@/lib/utils'

type MembershipSubscriptionButtonProps = {
    mode?: 'inline' | 'floating'
}

function formatPrice(value: number) {
    const hasDecimals = value % 1 !== 0
    return new Intl.NumberFormat('zh-CN', {
        minimumFractionDigits: hasDecimals ? 1 : 0,
        maximumFractionDigits: 2,
    }).format(value)
}

function getPlanMap(catalog: MembershipCatalog | null) {
    return new Map((catalog?.plans || []).map((plan) => [plan.id, plan]))
}

export default function MembershipSubscriptionButton({
    mode = 'inline',
}: MembershipSubscriptionButtonProps) {
    const router = useRouter()
    const [open, setOpen] = useState(false)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [catalog, setCatalog] = useState<MembershipCatalog | null>(null)
    const [currentMembership, setCurrentMembership] = useState<CurrentMembership | null>(null)
    const [membershipMode, setMembershipMode] = useState<MembershipMode>('personal')
    const [teamSize, setTeamSize] = useState(2)
    const [selectedPlan, setSelectedPlan] = useState<BillingPlan>('monthly')

    useEffect(() => {
        if (!open) return

        const previousOverflow = document.body.style.overflow
        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') setOpen(false)
        }

        document.body.style.overflow = 'hidden'
        document.addEventListener('keydown', handleEscape)

        return () => {
            document.body.style.overflow = previousOverflow
            document.removeEventListener('keydown', handleEscape)
        }
    }, [open])

    const loadMembershipData = async () => {
        setLoading(true)
        setError('')
        try {
            const response = await fetch('/api/membership', { cache: 'no-store' })
            const data = (await response.json()) as MembershipOverviewResponse
            if (!response.ok || !data.success) {
                throw new Error(data.error || '会员信息加载失败，请稍后重试。')
            }

            setCatalog(data.catalog)
            setCurrentMembership(data.current_membership)

            if (data.current_membership?.status === 'active' && data.current_membership.plan_id) {
                setMembershipMode(data.current_membership.mode)
                setSelectedPlan(data.current_membership.plan_id)
                setTeamSize(Math.max(2, data.current_membership.team_size || 2))
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : '会员信息加载失败，请稍后重试。')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        if (!open) return
        void loadMembershipData()
    }, [open])

    const buttonClassName =
        mode === 'floating'
            ? 'inline-flex h-12 items-center gap-2 rounded-xl border border-amber-300/80 bg-white/90 px-4 text-sm font-semibold text-amber-900 shadow-xl backdrop-blur transition hover:-translate-y-0.5 hover:bg-white dark:border-amber-300/30 dark:bg-slate-900/85 dark:text-amber-100 dark:hover:bg-slate-900'
            : 'inline-flex h-11 items-center gap-2 rounded-xl border border-amber-300/80 bg-white/90 px-4 text-sm font-semibold text-amber-900 shadow-lg backdrop-blur transition hover:-translate-y-0.5 hover:bg-white dark:border-amber-300/30 dark:bg-slate-900/80 dark:text-amber-100 dark:hover:bg-slate-900'

    const planMap = useMemo(() => getPlanMap(catalog), [catalog])
    const activePlan = selectedPlan ? planMap.get(selectedPlan) || null : null
    const normalizedTeamSize = membershipMode === 'team' ? Math.max(2, teamSize) : 1
    const teamDiscount = catalog?.team_discount || 1
    const isActiveMember = currentMembership?.status === 'active'

    const preview = useMemo(() => {
        if (!activePlan) return null
        const unitPrice = membershipMode === 'team' ? activePlan.base_price * teamDiscount : activePlan.base_price
        const totalPrice = membershipMode === 'team' ? unitPrice * normalizedTeamSize : unitPrice
        const quotaTotal = activePlan.quota_total
            ? activePlan.quota_total * (membershipMode === 'team' ? normalizedTeamSize : 1)
            : 0
        return { unitPrice, totalPrice, quotaTotal }
    }, [activePlan, membershipMode, normalizedTeamSize, teamDiscount])

    const handleGoCheckout = () => {
        if (!activePlan) {
            setError('请先选择一个订阅方案。')
            return
        }

        const params = new URLSearchParams({
            mode: membershipMode,
            plan: activePlan.id,
            teamSize: String(normalizedTeamSize),
        })
        setOpen(false)
        router.push(`/membership/checkout?${params.toString()}`)
    }

    return (
        <>
            <button
                type="button"
                onClick={() => setOpen(true)}
                className={buttonClassName}
                aria-label="打开会员订阅"
            >
                <Crown className="h-4 w-4" />
                <span>会员订阅</span>
            </button>

            {open ? (
                <div
                    className="fixed inset-0 z-[70] flex items-center justify-center bg-[rgba(15,23,42,0.48)] p-4 sm:p-6"
                    onClick={() => setOpen(false)}
                >
                    <div
                        className="animate-scale-up w-full max-w-[920px] overflow-hidden rounded-[30px] border border-[#E5E5E5] bg-[#FCFBF8] shadow-[0_28px_90px_rgba(17,17,17,0.26)] dark:border-[#2d3542] dark:bg-[#181c24]"
                        onClick={(event) => event.stopPropagation()}
                    >
                        <div className="border-b border-[#ECE7DD] bg-[linear-gradient(135deg,#fffaf0_0%,#f6f1e5_55%,#efe7d4_100%)] px-6 py-5 dark:border-[#2d3542] dark:bg-[linear-gradient(135deg,#202735_0%,#1b2230_55%,#161c27_100%)] sm:px-7 sm:py-6">
                            <div className="flex items-start justify-between gap-4">
                                <div className="flex-1">
                                    <div className="inline-flex items-center gap-2 rounded-full border border-amber-300/70 bg-white/80 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-amber-800 dark:border-amber-300/20 dark:bg-slate-900/55 dark:text-amber-100">
                                        <Sparkles className="h-3.5 w-3.5" />
                                        Premium Plan
                                    </div>
                                    <h2 className="mt-3 text-2xl font-semibold text-[#111111] dark:text-[#f4f7fb] sm:text-3xl">
                                        选择适合你的训练订阅方案
                                    </h2>
                                </div>

                                <div className="flex items-start gap-3">
                                    <div
                                        className={cn(
                                            'inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium',
                                            isActiveMember
                                                ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-300'
                                                : 'border-[#E5DED0] bg-white/80 text-[#6E675D] dark:border-[#3a4658] dark:bg-[#1b2230] dark:text-[#bcc5d3]',
                                        )}
                                    >
                                        <CheckCircle2 className="h-3.5 w-3.5" />
                                        <span>{isActiveMember ? '当前为会员' : '当前未开通'}</span>
                                    </div>

                                    <button
                                        type="button"
                                        onClick={() => setOpen(false)}
                                        className="inline-flex h-10 w-10 items-center justify-center rounded-full text-[#666666] transition hover:bg-white/80 hover:text-[#111111] dark:text-[#bcc5d3] dark:hover:bg-[#252b36] dark:hover:text-[#f4f7fb]"
                                        aria-label="关闭会员订阅"
                                    >
                                        <X className="h-5 w-5" />
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div className="space-y-5 px-6 py-5 sm:px-7 sm:py-6">
                            <section className="rounded-[26px] border border-[#E5E5E5] bg-white/92 p-5 shadow-[0_10px_28px_rgba(17,17,17,0.05)] dark:border-[#2d3542] dark:bg-[#1b2029]">
                                <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                                    <div className="flex-1">
                                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#8A7350] dark:text-[#d2dae8]">
                                            订阅类型
                                        </p>
                                        <div className="mt-3 inline-flex w-full rounded-2xl border border-[#E5E5E5] bg-[#FAF7F1] p-1 dark:border-[#2d3542] dark:bg-[#202735]">
                                            <button
                                                type="button"
                                                onClick={() => setMembershipMode('personal')}
                                                className={cn(
                                                    'inline-flex flex-1 items-center justify-center gap-2 rounded-[14px] px-4 py-3 text-sm font-medium transition',
                                                    membershipMode === 'personal'
                                                        ? 'bg-[#111111] text-white dark:bg-[#f4f7fb] dark:text-[#101217]'
                                                        : 'text-[#6E675D] hover:bg-white dark:text-[#bcc5d3] dark:hover:bg-[#252b36]',
                                                )}
                                            >
                                                <Crown className="h-4 w-4" />
                                                个人版
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => setMembershipMode('team')}
                                                className={cn(
                                                    'inline-flex flex-1 items-center justify-center gap-2 rounded-[14px] px-4 py-3 text-sm font-medium transition',
                                                    membershipMode === 'team'
                                                        ? 'bg-[#111111] text-white dark:bg-[#f4f7fb] dark:text-[#101217]'
                                                        : 'text-[#6E675D] hover:bg-white dark:text-[#bcc5d3] dark:hover:bg-[#252b36]',
                                                )}
                                            >
                                                <Users className="h-4 w-4" />
                                                团队版
                                            </button>
                                        </div>
                                    </div>

                                    {membershipMode === 'team' ? (
                                        <div className="min-w-[260px] rounded-2xl bg-[#F7F2E8] px-4 py-3 dark:bg-[#222834]">
                                            <div className="flex items-center justify-between gap-3">
                                                <div>
                                                    <p className="text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">
                                                        团队人数
                                                    </p>
                                                    <p className="mt-1 text-xs leading-5 text-[#7B746A] dark:text-[#9aa7bd]">
                                                        团队版 2 人起订，当前按 {Math.round(teamDiscount * 100)} 折计算。
                                                    </p>
                                                </div>
                                                <div className="inline-flex items-center gap-2">
                                                    <button
                                                        type="button"
                                                        onClick={() => setTeamSize((current) => Math.max(2, current - 1))}
                                                        className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-[#D9D3C7] bg-white text-[#111111] transition hover:bg-[#F3EFE6] dark:border-[#3b4452] dark:bg-[#181c24] dark:text-[#f4f7fb] dark:hover:bg-[#252b36]"
                                                        aria-label="减少团队人数"
                                                    >
                                                        <Minus className="h-4 w-4" />
                                                    </button>
                                                    <div className="min-w-[56px] text-center">
                                                        <p className="text-lg font-semibold text-[#111111] dark:text-[#f4f7fb]">
                                                            {normalizedTeamSize}
                                                        </p>
                                                        <p className="text-[10px] uppercase tracking-[0.14em] text-[#8A8277] dark:text-[#9aa7bd]">
                                                            Seats
                                                        </p>
                                                    </div>
                                                    <button
                                                        type="button"
                                                        onClick={() => setTeamSize((current) => Math.min(50, current + 1))}
                                                        className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-[#D9D3C7] bg-white text-[#111111] transition hover:bg-[#F3EFE6] dark:border-[#3b4452] dark:bg-[#181c24] dark:text-[#f4f7fb] dark:hover:bg-[#252b36]"
                                                        aria-label="增加团队人数"
                                                    >
                                                        <Plus className="h-4 w-4" />
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    ) : null}
                                </div>
                            </section>

                            {loading ? (
                                <div className="flex items-center justify-center rounded-[26px] border border-dashed border-[#E5E5E5] bg-white/70 px-6 py-10 text-sm text-[#6E675D] dark:border-[#2d3542] dark:bg-[#1b2029] dark:text-[#bcc5d3]">
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    正在加载会员套餐...
                                </div>
                            ) : (
                                <section className="grid gap-4 md:grid-cols-3">
                                    {(catalog?.plans || []).map((plan: MembershipPlan) => {
                                        const isSelected = selectedPlan === plan.id
                                        const isCurrentPlan =
                                            currentMembership?.status === 'active' &&
                                            currentMembership.plan_id === plan.id
                                        const planUnitPrice =
                                            membershipMode === 'team'
                                                ? plan.base_price * teamDiscount
                                                : plan.base_price
                                        const planTotalPrice =
                                            membershipMode === 'team'
                                                ? planUnitPrice * normalizedTeamSize
                                                : planUnitPrice
                                        const planQuota =
                                            plan.quota_total && plan.quota_total > 0
                                                ? plan.quota_total *
                                                  (membershipMode === 'team' ? normalizedTeamSize : 1)
                                                : 0

                                        return (
                                            <div
                                                key={plan.id}
                                                className={cn(
                                                    'flex min-h-[312px] flex-col rounded-[28px] border bg-white shadow-[0_12px_36px_rgba(17,17,17,0.06)] transition dark:bg-[#1b2029]',
                                                    isSelected
                                                        ? 'border-[#111111] ring-1 ring-[#111111] dark:border-[#f4f7fb] dark:ring-[#f4f7fb]'
                                                        : 'border-[#E5E5E5] dark:border-[#2d3542]',
                                                )}
                                            >
                                                <div className="px-6 py-6">
                                                    <div className="flex items-start justify-between gap-3">
                                                        <div>
                                                            <h3 className="text-lg font-medium tracking-tight text-[#111111] dark:text-[#f4f7fb] lg:text-2xl">
                                                                {plan.title}
                                                            </h3>
                                                            <p className="mt-2 text-sm leading-6 text-[#7B746A] dark:text-[#9aa7bd]">
                                                                {plan.description}
                                                            </p>
                                                        </div>
                                                        <div className="flex flex-col items-end gap-2">
                                                            {plan.highlight ? (
                                                                <span className="inline-flex whitespace-nowrap rounded-full bg-[#F3EFE6] px-3 py-1 text-xs font-medium text-[#8A7350] dark:bg-[#252b36] dark:text-[#d2dae8]">
                                                                    {plan.highlight}
                                                                </span>
                                                            ) : null}
                                                            {isCurrentPlan ? (
                                                                <span className="inline-flex whitespace-nowrap rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">
                                                                    当前方案
                                                                </span>
                                                            ) : null}
                                                        </div>
                                                    </div>

                                                    <div className="mt-6">
                                                        <p className="flex items-end gap-2">
                                                            <span className="text-4xl font-light tracking-tight text-[#111111] dark:text-[#f4f7fb] sm:text-5xl">
                                                                ¥{formatPrice(planTotalPrice)}
                                                            </span>
                                                            <span className="pb-1 text-sm font-medium text-[#7B746A] dark:text-[#9aa7bd]">
                                                                {plan.unit_label}
                                                            </span>
                                                        </p>
                                                        <p className="mt-3 text-sm leading-6 text-[#6E675D] dark:text-[#bcc5d3]">
                                                            {membershipMode === 'team'
                                                                ? `折后单价 ¥${formatPrice(planUnitPrice)}${plan.unit_label}，共 ${normalizedTeamSize} 人。`
                                                                : plan.detail}
                                                        </p>
                                                    </div>
                                                </div>

                                                <div className="mt-auto flex px-6 pb-6">
                                                    <button
                                                        type="button"
                                                        onClick={() => setSelectedPlan(plan.id)}
                                                        className={cn(
                                                            'inline-flex w-full items-center justify-center rounded-full border-2 px-6 py-3 text-sm font-medium transition',
                                                            isSelected
                                                                ? 'border-[#111111] bg-[#111111] text-white hover:bg-transparent hover:text-[#111111] dark:border-[#f4f7fb] dark:bg-[#f4f7fb] dark:text-[#101217] dark:hover:bg-transparent dark:hover:text-[#f4f7fb]'
                                                                : 'border-[#111111] bg-transparent text-[#111111] hover:bg-[#111111] hover:text-white dark:border-[#f4f7fb] dark:text-[#f4f7fb] dark:hover:bg-[#f4f7fb] dark:hover:text-[#101217]',
                                                        )}
                                                    >
                                                        {isSelected ? '当前选择' : '选择此方案'}
                                                    </button>
                                                </div>
                                            </div>
                                        )
                                    })}
                                </section>
                            )}

                            {error ? (
                                <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/20 dark:text-red-300">
                                    {error}
                                </div>
                            ) : null}

                            <section className="rounded-[26px] border border-[#E5E5E5] bg-white/92 p-5 shadow-[0_10px_28px_rgba(17,17,17,0.05)] dark:border-[#2d3542] dark:bg-[#1b2029]">
                                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                                    <div>
                                        <p className="text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">
                                            已选方案
                                        </p>
                                        <p className="mt-2 text-sm leading-6 text-[#6E675D] dark:text-[#bcc5d3]">
                                            {membershipMode === 'team' ? `团队版 ${normalizedTeamSize} 人` : '个人版'} ·{' '}
                                            {activePlan?.title || '请选择订阅方案'}
                                        </p>
                                        <p className="mt-2 text-2xl font-semibold text-[#111111] dark:text-[#f4f7fb]">
                                            ¥{formatPrice(preview?.totalPrice || 0)}
                                        </p>
                                        {preview?.quotaTotal ? (
                                            <p className="mt-2 text-sm text-[#7B746A] dark:text-[#9aa7bd]">
                                                预计包含 {preview.quotaTotal} 次训练额度。
                                            </p>
                                        ) : null}
                                    </div>

                                    <div className="flex flex-wrap gap-3">
                                        <button
                                            type="button"
                                            onClick={handleGoCheckout}
                                            disabled={!activePlan || loading}
                                            className="inline-flex items-center justify-center rounded-full border-2 border-[#111111] bg-[#111111] px-5 py-3 text-sm font-medium text-white transition hover:bg-transparent hover:text-[#111111] disabled:cursor-not-allowed disabled:opacity-60 dark:border-[#f4f7fb] dark:bg-[#f4f7fb] dark:text-[#101217] dark:hover:bg-transparent dark:hover:text-[#f4f7fb]"
                                        >
                                            前往订单与支付
                                        </button>
                                    </div>
                                </div>
                            </section>
                        </div>
                    </div>
                </div>
            ) : null}
        </>
    )
}

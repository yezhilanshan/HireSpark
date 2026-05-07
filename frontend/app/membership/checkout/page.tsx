'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import {
    ArrowLeft,
    CheckCircle2,
    CreditCard,
    Loader2,
    Receipt,
    Sparkles,
} from 'lucide-react'
import PersistentSidebar from '@/components/PersistentSidebar'
import type {
    BillingPlan,
    CurrentMembership,
    MembershipCatalog,
    MembershipMode,
    MembershipOrder,
    MembershipOverviewResponse,
    MembershipPlan,
} from '@/lib/membership'

type OrderResponse = {
    success: boolean
    error?: string
    order?: MembershipOrder
    current_membership?: CurrentMembership
    message?: string
}

function formatPrice(value: number) {
    const hasDecimals = value % 1 !== 0
    return new Intl.NumberFormat('zh-CN', {
        minimumFractionDigits: hasDecimals ? 1 : 0,
        maximumFractionDigits: 2,
    }).format(value)
}

function formatDateTime(value?: string | null) {
    if (!value) return '长期有效'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return value
    return new Intl.DateTimeFormat('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
    }).format(date)
}

function getPlanMap(catalog: MembershipCatalog | null) {
    return new Map((catalog?.plans || []).map((plan) => [plan.id, plan]))
}

export default function MembershipCheckoutPage() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const [loading, setLoading] = useState(true)
    const [submitting, setSubmitting] = useState(false)
    const [error, setError] = useState('')
    const [message, setMessage] = useState('')
    const [catalog, setCatalog] = useState<MembershipCatalog | null>(null)
    const [currentMembership, setCurrentMembership] = useState<CurrentMembership | null>(null)
    const [recentOrders, setRecentOrders] = useState<MembershipOrder[]>([])
    const [pendingOrder, setPendingOrder] = useState<MembershipOrder | null>(null)

    const requestedMode = (searchParams.get('mode') || 'personal') as MembershipMode
    const requestedPlan = (searchParams.get('plan') || 'monthly') as BillingPlan
    const requestedTeamSize = Math.max(2, Number(searchParams.get('teamSize') || 2))

    const loadMembershipData = async () => {
        setLoading(true)
        setError('')
        try {
            const response = await fetch('/api/membership', { cache: 'no-store' })
            const data = (await response.json()) as MembershipOverviewResponse
            if (!response.ok || !data.success) {
                throw new Error(data.error || '会员信息加载失败')
            }

            setCatalog(data.catalog)
            setCurrentMembership(data.current_membership)
            setRecentOrders(data.recent_orders || [])
        } catch (err) {
            setError(err instanceof Error ? err.message : '会员信息加载失败')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        void loadMembershipData()
    }, [])

    const planMap = useMemo(() => getPlanMap(catalog), [catalog])
    const selectedMode: MembershipMode = requestedMode === 'team' ? 'team' : 'personal'
    const selectedTeamSize = selectedMode === 'team' ? requestedTeamSize : 1
    const selectedPlan = planMap.get(requestedPlan) || catalog?.plans?.[0] || null
    const teamDiscount = catalog?.team_discount || 1

    const preview = useMemo(() => {
        if (!selectedPlan) return null
        const unitPrice = selectedMode === 'team'
            ? selectedPlan.base_price * teamDiscount
            : selectedPlan.base_price
        const totalPrice = selectedMode === 'team' ? unitPrice * selectedTeamSize : unitPrice
        const quotaTotal = selectedPlan.quota_total
            ? selectedPlan.quota_total * (selectedMode === 'team' ? selectedTeamSize : 1)
            : 0
        return { unitPrice, totalPrice, quotaTotal }
    }, [selectedMode, selectedPlan, selectedTeamSize, teamDiscount])

    useEffect(() => {
        if (!recentOrders.length) {
            setPendingOrder(null)
            return
        }
        const matchedOrder =
            recentOrders.find(
                (order) =>
                    order.status === 'pending' &&
                    order.plan_id === requestedPlan &&
                    order.membership_mode === selectedMode &&
                    order.team_size === selectedTeamSize,
            ) || null
        setPendingOrder(matchedOrder)
    }, [recentOrders, requestedPlan, selectedMode, selectedTeamSize])

    const handleCreateOrder = async () => {
        if (!selectedPlan) {
            setError('当前没有可用订阅方案。')
            return
        }

        setSubmitting(true)
        setError('')
        setMessage('')
        try {
            const response = await fetch('/api/membership', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    membership_mode: selectedMode,
                    plan_id: selectedPlan.id,
                    team_size: selectedTeamSize,
                }),
            })
            const data = (await response.json()) as OrderResponse
            if (!response.ok || !data.success || !data.order) {
                throw new Error(data.error || '创建订单失败')
            }

            setPendingOrder(data.order)
            setMessage('订单已创建，请继续完成支付开通。')
            await loadMembershipData()
        } catch (err) {
            setError(err instanceof Error ? err.message : '创建订单失败')
        } finally {
            setSubmitting(false)
        }
    }

    const handlePayOrder = async () => {
        if (!pendingOrder) {
            setError('请先创建订单。')
            return
        }

        setSubmitting(true)
        setError('')
        setMessage('')
        try {
            const response = await fetch('/api/membership/pay', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ order_id: pendingOrder.order_id }),
            })
            const data = (await response.json()) as OrderResponse
            if (!response.ok || !data.success) {
                throw new Error(data.error || '支付开通失败')
            }

            setPendingOrder(null)
            setCurrentMembership(data.current_membership || null)
            setMessage(data.message || '会员已开通')
            await loadMembershipData()
        } catch (err) {
            setError(err instanceof Error ? err.message : '支付开通失败')
        } finally {
            setSubmitting(false)
        }
    }

    return (
        <div className="flex min-h-screen bg-[#F6F2EB] dark:bg-[#0C1017]">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="min-h-screen px-5 py-6 text-[#1D1D1B] dark:text-[#EEF2F8] sm:px-6 lg:px-8">
                    <div className="mx-auto flex w-full max-w-[1320px] flex-col gap-6">
                        <section className="rounded-[34px] border border-[#E5DED0] bg-white/88 p-6 shadow-[0_18px_60px_rgba(17,17,17,0.06)] backdrop-blur sm:p-8 dark:border-[#283140] dark:bg-[#10151E]/90">
                            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                                <div className="space-y-3">
                                    <div className="inline-flex items-center gap-2 rounded-full border border-[#EAE2D5] bg-[#FBF7F0] px-3 py-1 text-xs font-semibold tracking-[0.18em] text-[#8B6F3D] dark:border-[#3A4658] dark:bg-[#141A23] dark:text-[#D6C7A6]">
                                        <Sparkles className="h-3.5 w-3.5" />
                                        ORDER & PAYMENT
                                    </div>
                                    <div className="space-y-2">
                                        <h1 className="font-serif text-4xl tracking-tight text-[#171717] dark:text-white">
                                            订单与支付
                                        </h1>
                                        <p className="max-w-3xl text-sm leading-7 text-[#666257] dark:text-[#B8C2D3]">
                                            这里专门处理会员订单创建、支付开通和最近订单记录，避免套餐弹窗因为信息过多而看不全。
                                        </p>
                                    </div>
                                </div>

                                <button
                                    type="button"
                                    onClick={() => router.back()}
                                    className="inline-flex items-center gap-2 rounded-2xl border border-[#DDD2BE] bg-[#FBF7F0] px-4 py-2 text-sm font-medium text-[#5B4B2E] transition hover:bg-[#F6EFDF] dark:border-[#364253] dark:bg-[#151D29] dark:text-[#E3D3B0] dark:hover:bg-[#1A2432]"
                                >
                                    <ArrowLeft className="h-4 w-4" />
                                    返回上一页
                                </button>
                            </div>
                        </section>

                        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_360px]">
                            <div className="space-y-6">
                                <div className="rounded-[30px] border border-[#E5DED0] bg-white/88 p-6 shadow-[0_14px_40px_rgba(17,17,17,0.05)] dark:border-[#283140] dark:bg-[#10151E]/90">
                                    <div className="flex items-center gap-2">
                                        <Receipt className="h-5 w-5 text-[#8A7350] dark:text-[#D6C7A6]" />
                                        <h2 className="font-serif text-2xl text-[#171717] dark:text-white">
                                            本次订单预览
                                        </h2>
                                    </div>

                                    {loading ? (
                                        <div className="mt-5 flex items-center text-sm text-[#6E675D] dark:text-[#bcc5d3]">
                                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                            正在加载会员信息...
                                        </div>
                                    ) : (
                                        <div className="mt-5 grid gap-4 sm:grid-cols-2">
                                            <div className="rounded-[24px] border border-[#E5E5E5] bg-[#FAF7F1] p-5 dark:border-[#2d3542] dark:bg-[#1c2330]">
                                                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#8A7350] dark:text-[#d2dae8]">
                                                    订阅对象
                                                </p>
                                                <p className="mt-3 text-lg font-semibold text-[#111111] dark:text-[#f4f7fb]">
                                                    {selectedMode === 'team' ? `团队版 ${selectedTeamSize} 人` : '个人版'}
                                                </p>
                                                <p className="mt-2 text-sm leading-6 text-[#6E675D] dark:text-[#bcc5d3]">
                                                    {selectedMode === 'team'
                                                        ? `按团队版折扣计算，当前共 ${selectedTeamSize} 个席位。`
                                                        : '按单人标准价计算，可直接完成开通。'}
                                                </p>
                                            </div>

                                            <div className="rounded-[24px] border border-[#E5E5E5] bg-[#FAF7F1] p-5 dark:border-[#2d3542] dark:bg-[#1c2330]">
                                                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#8A7350] dark:text-[#d2dae8]">
                                                    当前方案
                                                </p>
                                                <p className="mt-3 text-lg font-semibold text-[#111111] dark:text-[#f4f7fb]">
                                                    {selectedPlan?.title || '暂无方案'}
                                                </p>
                                                <p className="mt-2 text-sm leading-6 text-[#6E675D] dark:text-[#bcc5d3]">
                                                    {selectedPlan?.description || '请返回会员弹窗重新选择套餐。'}
                                                </p>
                                            </div>
                                        </div>
                                    )}

                                    <div className="mt-5 rounded-[24px] border border-[#E5E5E5] bg-white p-5 dark:border-[#2d3542] dark:bg-[#181c24]">
                                        <div className="flex flex-wrap items-end justify-between gap-4">
                                            <div>
                                                <p className="text-sm text-[#6E675D] dark:text-[#bcc5d3]">应付金额</p>
                                                <p className="mt-2 text-4xl font-light text-[#111111] dark:text-[#f4f7fb]">
                                                    ¥{formatPrice(preview?.totalPrice || 0)}
                                                </p>
                                            </div>
                                            <div className="text-sm leading-6 text-[#6E675D] dark:text-[#bcc5d3]">
                                                <p>
                                                    单价：¥{formatPrice(preview?.unitPrice || 0)}
                                                    {selectedPlan?.unit_label || ''}
                                                </p>
                                                {preview?.quotaTotal ? (
                                                    <p>本次开通将获得 {preview.quotaTotal} 次使用额度。</p>
                                                ) : null}
                                            </div>
                                        </div>
                                    </div>

                                    {pendingOrder ? (
                                        <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200">
                                            已创建待支付订单 {pendingOrder.order_id}，金额 ¥{formatPrice(pendingOrder.total_price)}。
                                        </div>
                                    ) : null}

                                    {error ? (
                                        <div className="mt-5 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/20 dark:text-red-300">
                                            {error}
                                        </div>
                                    ) : null}

                                    {message ? (
                                        <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-300">
                                            {message}
                                        </div>
                                    ) : null}

                                    <div className="mt-5 flex flex-wrap gap-3">
                                        <button
                                            type="button"
                                            onClick={() => void handleCreateOrder()}
                                            disabled={submitting || loading || !selectedPlan}
                                            className="inline-flex items-center justify-center rounded-full border-2 border-[#111111] bg-transparent px-5 py-3 text-sm font-medium text-[#111111] transition hover:bg-[#111111] hover:text-white disabled:cursor-not-allowed disabled:opacity-60 dark:border-[#f4f7fb] dark:text-[#f4f7fb] dark:hover:bg-[#f4f7fb] dark:hover:text-[#101217]"
                                        >
                                            {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                                            创建订单
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => void handlePayOrder()}
                                            disabled={submitting || !pendingOrder}
                                            className="inline-flex items-center justify-center rounded-full border-2 border-[#111111] bg-[#111111] px-5 py-3 text-sm font-medium text-white transition hover:bg-transparent hover:text-[#111111] disabled:cursor-not-allowed disabled:opacity-60 dark:border-[#f4f7fb] dark:bg-[#f4f7fb] dark:text-[#101217] dark:hover:bg-transparent dark:hover:text-[#f4f7fb]"
                                        >
                                            {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                                            <CreditCard className="mr-2 h-4 w-4" />
                                            立即支付并开通
                                        </button>
                                        <Link
                                            href="/dashboard"
                                            className="inline-flex items-center justify-center rounded-full border border-[#DDD2BE] bg-[#FBF7F0] px-5 py-3 text-sm font-medium text-[#5B4B2E] transition hover:bg-[#F6EFDF] dark:border-[#364253] dark:bg-[#151D29] dark:text-[#E3D3B0] dark:hover:bg-[#1A2432]"
                                        >
                                            稍后再说
                                        </Link>
                                    </div>
                                </div>
                            </div>

                            <div className="space-y-6">
                                <div className="rounded-[30px] border border-[#E5DED0] bg-white/88 p-6 shadow-[0_14px_40px_rgba(17,17,17,0.05)] dark:border-[#283140] dark:bg-[#10151E]/90">
                                    <div className="flex items-center gap-2">
                                        <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-300" />
                                        <h3 className="font-serif text-2xl text-[#171717] dark:text-white">
                                            当前会员状态
                                        </h3>
                                    </div>
                                    <p className="mt-4 text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">
                                        {currentMembership?.status === 'active'
                                            ? `${currentMembership.mode === 'team' ? `团队版 ${currentMembership.team_size} 人` : '个人版'} · ${currentMembership.plan_title || '已开通'}`
                                            : '当前未开通会员'}
                                    </p>
                                    <p className="mt-2 text-sm leading-6 text-[#6E675D] dark:text-[#bcc5d3]">
                                        {currentMembership?.status === 'active'
                                            ? `生效时间 ${formatDateTime(currentMembership.started_at)}，到期时间 ${formatDateTime(currentMembership.expires_at)}。`
                                            : '开通后这里会同步展示你的当前方案、到期时间和剩余可用额度。'}
                                    </p>

                                    {currentMembership?.status === 'active' && currentMembership.usage.total > 0 ? (
                                        <div className="mt-4 rounded-2xl bg-[#F7F2E8] p-4 dark:bg-[#222834]">
                                            <div className="flex items-center justify-between gap-3 text-sm">
                                                <span className="font-medium text-[#111111] dark:text-[#f4f7fb]">
                                                    使用次数消耗
                                                </span>
                                                <span className="text-[#6E675D] dark:text-[#bcc5d3]">
                                                    {currentMembership.usage.used}/{currentMembership.usage.total}
                                                </span>
                                            </div>
                                            <div className="mt-3 h-2 overflow-hidden rounded-full bg-white dark:bg-[#181c24]">
                                                <div
                                                    className="h-full rounded-full bg-[#111111] dark:bg-[#f4f7fb]"
                                                    style={{
                                                        width: `${Math.min(
                                                            100,
                                                            currentMembership.usage.total > 0
                                                                ? (currentMembership.usage.used /
                                                                      currentMembership.usage.total) *
                                                                      100
                                                                : 0,
                                                        )}%`,
                                                    }}
                                                />
                                            </div>
                                            <p className="mt-3 text-xs leading-5 text-[#7B746A] dark:text-[#9aa7bd]">
                                                还可使用 {currentMembership.usage.remaining} 次。
                                            </p>
                                        </div>
                                    ) : null}
                                </div>

                                <div className="rounded-[30px] border border-[#E5DED0] bg-white/88 p-6 shadow-[0_14px_40px_rgba(17,17,17,0.05)] dark:border-[#283140] dark:bg-[#10151E]/90">
                                    <h3 className="font-serif text-2xl text-[#171717] dark:text-white">最近订单</h3>
                                    <div className="mt-4 space-y-3">
                                        {recentOrders.slice(0, 4).map((order) => (
                                            <div
                                                key={order.order_id}
                                                className="rounded-2xl border border-[#E5E5E5] bg-[#FAF7F1] px-4 py-3 text-sm dark:border-[#2d3542] dark:bg-[#202735]"
                                            >
                                                <div className="flex items-center justify-between gap-3">
                                                    <span className="font-medium text-[#111111] dark:text-[#f4f7fb]">
                                                        {order.plan_title || order.plan_id}
                                                    </span>
                                                    <span
                                                        className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                                                            order.status === 'paid'
                                                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300'
                                                                : 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300'
                                                        }`}
                                                    >
                                                        {order.status === 'paid' ? '已支付' : '待支付'}
                                                    </span>
                                                </div>
                                                <p className="mt-2 text-xs leading-5 text-[#7B746A] dark:text-[#9aa7bd]">
                                                    {order.membership_mode === 'team' ? `团队版 ${order.team_size} 人` : '个人版'} ·
                                                    ¥{formatPrice(order.total_price)}
                                                </p>
                                            </div>
                                        ))}
                                        {!recentOrders.length ? (
                                            <div className="rounded-2xl border border-dashed border-[#E5E5E5] px-4 py-6 text-sm text-[#6E675D] dark:border-[#2d3542] dark:text-[#bcc5d3]">
                                                还没有会员订单，创建后会出现在这里。
                                            </div>
                                        ) : null}
                                    </div>
                                </div>
                            </div>
                        </section>
                    </div>
                </div>
            </main>
        </div>
    )
}

'use client'

import { FormEvent, Suspense, useMemo, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { resolveSafeRedirect } from '@/lib/auth'

function LoginPageContent() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const redirectTarget = useMemo(() => resolveSafeRedirect(searchParams.get('next')), [searchParams])

    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [isSubmitting, setIsSubmitting] = useState(false)

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        if (isSubmitting) return

        const normalizedEmail = email.trim().toLowerCase()
        if (!normalizedEmail || !password.trim()) {
            setError('请输入完整的邮箱和密码。')
            return
        }

        setIsSubmitting(true)
        setError('')

        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: normalizedEmail,
                    password,
                }),
            })
            const data = await response.json().catch(() => ({}))

            if (!response.ok || !data?.success) {
                throw new Error(data?.error || '登录失败，请稍后重试。')
            }

            router.replace(redirectTarget)
            router.refresh()
        } catch (err) {
            setError(err instanceof Error ? err.message : '登录失败，请稍后重试。')
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <div className="min-h-screen bg-[#FAF9F6] lg:grid lg:grid-cols-[1.05fr_0.95fr]">
            <section className="hidden border-r border-[#E5E5E5] bg-[#F4F2EC] lg:flex lg:flex-col lg:justify-between lg:p-12">
                <div className="text-xl font-serif italic font-medium text-[#111111]">PanelMind</div>

                <div className="max-w-xl space-y-6">
                    <h1 className="font-serif text-5xl leading-[1.08] tracking-tight text-[#111111]">
                        打磨表达逻辑。
                        <br />
                        进入真实面试状态。
                    </h1>
                    <p className="max-w-lg text-lg leading-8 text-[#666666]">
                        PanelMind 为候选人提供结构化模拟面试、即时评分报告与逐题复盘，
                        帮你把每一轮练习都沉淀成可追踪的提升。
                    </p>
                </div>

                <div className="text-sm text-[#999999]">© 2026 PanelMind</div>
            </section>

            <section className="flex items-center justify-center px-6 py-10 sm:px-8 lg:px-12">
                <div className="w-full max-w-md rounded-[32px] border border-[#E5E5E5] bg-white p-8 shadow-[0_24px_80px_rgba(17,17,17,0.06)] sm:p-10">
                    <div className="space-y-3">
                        <div className="text-xl font-serif italic font-medium text-[#111111] lg:hidden">PanelMind</div>
                        <h2 className="text-3xl font-semibold tracking-tight text-[#111111]">登录 PanelMind</h2>
                        <p className="text-sm leading-6 text-[#666666]">登录后继续进入你的工作台与面试训练空间。</p>
                    </div>

                    <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
                        <div className="space-y-2">
                            <label htmlFor="email" className="text-sm font-medium text-[#111111]">
                                邮箱
                            </label>
                            <input
                                id="email"
                                type="email"
                                autoComplete="email"
                                value={email}
                                onChange={(event) => setEmail(event.target.value)}
                                placeholder="请输入邮箱地址"
                                className="h-11 w-full rounded-xl border border-[#E5E5E5] bg-white px-4 text-sm text-[#111111] outline-none transition focus:border-[#111111] focus:ring-1 focus:ring-[#111111]"
                            />
                        </div>

                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <label htmlFor="password" className="text-sm font-medium text-[#111111]">
                                    密码
                                </label>
                                <span className="text-xs text-[#999999]">暂不开放找回密码</span>
                            </div>
                            <input
                                id="password"
                                type="password"
                                autoComplete="current-password"
                                value={password}
                                onChange={(event) => setPassword(event.target.value)}
                                placeholder="请输入密码"
                                className="h-11 w-full rounded-xl border border-[#E5E5E5] bg-white px-4 text-sm text-[#111111] outline-none transition focus:border-[#111111] focus:ring-1 focus:ring-[#111111]"
                            />
                        </div>

                        {error ? (
                            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                {error}
                            </div>
                        ) : null}

                        <Button type="submit" className="w-full" disabled={isSubmitting}>
                            {isSubmitting ? '登录中...' : '登录'}
                        </Button>
                    </form>

                    <div className="mt-6 rounded-2xl border border-[#EAE7DD] bg-[#FAF9F6] px-4 py-3 text-sm leading-6 text-[#666666]">
                        默认演示账号：admin@panelmind.cn
                        <br />
                        默认演示密码：PanelMind123
                    </div>
                </div>
            </section>
        </div>
    )
}

export default function LoginPage() {
    return (
        <Suspense fallback={<div className="min-h-screen bg-[#FAF9F6]" />}>
            <LoginPageContent />
        </Suspense>
    )
}

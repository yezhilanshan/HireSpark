'use client'

import { FormEvent, Suspense, useMemo, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { DEFAULT_LOGIN_EMAIL, DEFAULT_LOGIN_PASSWORD, resolveSafeRedirect } from '@/lib/auth'

type AuthMode = 'login' | 'register'

function LoginPageContent() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const redirectTarget = useMemo(() => resolveSafeRedirect(searchParams.get('next')), [searchParams])

    const [mode, setMode] = useState<AuthMode>('login')
    const [name, setName] = useState('')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [error, setError] = useState('')
    const [isSubmitting, setIsSubmitting] = useState(false)

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        if (isSubmitting) return

        const normalizedEmail = email.trim().toLowerCase()
        const normalizedName = name.trim()
        if (!normalizedEmail || !password.trim()) {
            setError('请输入完整的邮箱和密码。')
            return
        }

        if (mode === 'register') {
            if (!normalizedName) {
                setError('请输入昵称。')
                return
            }
            if (password.length < 8) {
                setError('密码长度至少为 8 位。')
                return
            }
            if (password !== confirmPassword) {
                setError('两次输入的密码不一致。')
                return
            }
        }

        setIsSubmitting(true)
        setError('')

        try {
            const response = await fetch(mode === 'register' ? '/api/auth/register' : '/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: normalizedName,
                    email: normalizedEmail,
                    password,
                }),
            })
            const data = await response.json().catch(() => ({}))

            if (!response.ok || !data?.success) {
                throw new Error(data?.error || (mode === 'register' ? '注册失败，请稍后重试。' : '登录失败，请稍后重试。'))
            }

            router.replace(redirectTarget)
            router.refresh()
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : mode === 'register'
                        ? '注册失败，请稍后重试。'
                        : '登录失败，请稍后重试。',
            )
        } finally {
            setIsSubmitting(false)
        }
    }

    const switchMode = (nextMode: AuthMode) => {
        if (isSubmitting || mode === nextMode) return
        setMode(nextMode)
        setError('')
    }

    return (
        <div className="min-h-screen bg-[var(--background)] lg:grid lg:grid-cols-[1.05fr_0.95fr]">
            <section className="hidden border-r border-[var(--border)] bg-[var(--surface)] lg:flex lg:flex-col lg:justify-between lg:p-12">
                <div className="text-xl font-serif italic font-medium text-[var(--ink)]">职跃星辰</div>

                <div className="max-w-xl space-y-6">
                    <h1 className="font-serif text-5xl leading-[1.08] tracking-tight text-[var(--ink)]">
                        打磨表达逻辑。
                        <br />
                        进入真实面试状态。
                    </h1>
                    <p className="max-w-lg text-lg leading-8 text-[var(--ink-muted)]">
                        职跃星辰 为候选人提供结构化模拟面试、即时评分报告与逐题复盘，
                        帮你把每一轮练习都沉淀成可追踪的提升。
                    </p>
                </div>

                <div className="text-sm text-[var(--ink-lighter)]">© 2026 职跃星辰</div>
            </section>

            <section className="flex items-center justify-center px-6 py-10 sm:px-8 lg:px-12">
                <div className="w-full max-w-md rounded-[32px] border border-[var(--border)] bg-[var(--surface)] p-8 shadow-[0_24px_80px_rgba(17,17,17,0.06)] sm:p-10">
                    <div className="space-y-4">
                        <div className="text-xl font-serif italic font-medium text-[var(--ink)] lg:hidden">职跃星辰</div>

                        <div className="inline-flex rounded-xl border border-[var(--border)] bg-[var(--background)] p-1">
                            <button
                                type="button"
                                className={`rounded-lg px-4 py-1.5 text-sm transition ${mode === 'login' ? 'bg-[var(--surface)] text-[var(--ink)] shadow-sm' : 'text-[var(--ink-muted)]'}`}
                                onClick={() => switchMode('login')}
                            >
                                登录
                            </button>
                            <button
                                type="button"
                                className={`rounded-lg px-4 py-1.5 text-sm transition ${mode === 'register' ? 'bg-[var(--surface)] text-[var(--ink)] shadow-sm' : 'text-[var(--ink-muted)]'}`}
                                onClick={() => switchMode('register')}
                            >
                                注册
                            </button>
                        </div>

                        <div className="space-y-2">
                            <h2 className="text-3xl font-semibold tracking-tight text-[var(--ink)]">
                                {mode === 'register' ? '注册 职跃星辰 账号' : '登录 职跃星辰'}
                            </h2>
                            <p className="text-sm leading-6 text-[var(--ink-muted)]">
                                {mode === 'register' ? '注册后可直接进入你的工作台与面试训练空间。' : '登录后继续进入你的工作台与面试训练空间。'}
                            </p>
                            {mode === 'login' ? (
                                <div className="rounded-xl border border-[var(--accent)]/30 bg-[var(--accent)]/5 px-4 py-3 text-xs text-[var(--ink-muted)]">
                                    <span className="font-medium text-[var(--ink)]">演示账号：</span>
                                    <span className="tabular-nums">admin@zhiyuexingchen.cn / 职跃星辰123</span>
                                </div>
                            ) : null}
                        </div>
                    </div>

                    <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
                        {mode === 'register' ? (
                            <div className="space-y-2">
                                <label htmlFor="name" className="text-sm font-medium text-[var(--ink)]">
                                    昵称
                                </label>
                                <input
                                    id="name"
                                    type="text"
                                    autoComplete="name"
                                    value={name}
                                    onChange={(event) => setName(event.target.value)}
                                    placeholder="请输入昵称"
                                    className="h-11 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 text-sm text-[var(--ink)] outline-none transition focus:border-[var(--ink)] focus:ring-1 focus:ring-[var(--ink)]"
                                />
                            </div>
                        ) : null}

                        <div className="space-y-2">
                            <label htmlFor="email" className="text-sm font-medium text-[var(--ink)]">
                                邮箱
                            </label>
                            <input
                                id="email"
                                type="email"
                                autoComplete="email"
                                value={email}
                                onChange={(event) => setEmail(event.target.value)}
                                placeholder="请输入邮箱地址"
                                className="h-11 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 text-sm text-[var(--ink)] outline-none transition focus:border-[var(--ink)] focus:ring-1 focus:ring-[var(--ink)]"
                            />
                        </div>

                        <div className="space-y-2">
                            <label htmlFor="password" className="text-sm font-medium text-[var(--ink)]">
                                密码
                            </label>
                            <input
                                id="password"
                                type="password"
                                autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                                value={password}
                                onChange={(event) => setPassword(event.target.value)}
                                placeholder={mode === 'register' ? '请输入至少 8 位密码' : '请输入密码'}
                                className="h-11 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 text-sm text-[var(--ink)] outline-none transition focus:border-[var(--ink)] focus:ring-1 focus:ring-[var(--ink)]"
                            />
                        </div>

                        {mode === 'register' ? (
                            <div className="space-y-2">
                                <label htmlFor="confirmPassword" className="text-sm font-medium text-[var(--ink)]">
                                    确认密码
                                </label>
                                <input
                                    id="confirmPassword"
                                    type="password"
                                    autoComplete="new-password"
                                    value={confirmPassword}
                                    onChange={(event) => setConfirmPassword(event.target.value)}
                                    placeholder="请再次输入密码"
                                    className="h-11 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 text-sm text-[var(--ink)] outline-none transition focus:border-[var(--ink)] focus:ring-1 focus:ring-[var(--ink)]"
                                />
                            </div>
                        ) : null}

                        {error ? (
                            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                {error}
                            </div>
                        ) : null}

                        <Button type="submit" className="w-full" disabled={isSubmitting}>
                            {isSubmitting ? (mode === 'register' ? '注册中...' : '登录中...') : (mode === 'register' ? '注册并进入' : '登录')}
                        </Button>
                    </form>

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

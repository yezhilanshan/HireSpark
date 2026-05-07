'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { ArrowLeft, Eye, EyeOff, KeyRound, Loader2, LogOut, Save } from 'lucide-react'
import PersistentSidebar from '@/components/PersistentSidebar'
import { getBackendBaseUrl } from '@/lib/backend'

const BACKEND_API_BASE = getBackendBaseUrl()

export default function AccountSecurityPage() {
    const [currentEmail, setCurrentEmail] = useState('')
    const [currentPassword, setCurrentPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [showCurrent, setShowCurrent] = useState(false)
    const [showNew, setShowNew] = useState(false)
    const [loading, setLoading] = useState(false)
    const [statusText, setStatusText] = useState('')
    const [statusType, setStatusType] = useState<'success' | 'error' | ''>('')

    useEffect(() => {
        const fetchUser = async () => {
            try {
                const response = await fetch('/api/auth/me', { cache: 'no-store' })
                const data = await response.json().catch(() => ({}))
                if (data?.user?.email) {
                    setCurrentEmail(data.user.email)
                }
            } catch {
                // ignore
            }
        }
        void fetchUser()
    }, [])

    const handleChangePassword = async () => {
        setStatusText('')
        setStatusType('')

        if (!currentPassword.trim()) {
            setStatusText('请输入当前密码。')
            setStatusType('error')
            return
        }
        if (!newPassword.trim()) {
            setStatusText('请输入新密码。')
            setStatusType('error')
            return
        }
        if (newPassword.length < 8) {
            setStatusText('新密码长度至少为 8 位。')
            setStatusType('error')
            return
        }
        if (newPassword !== confirmPassword) {
            setStatusText('两次输入的新密码不一致。')
            setStatusType('error')
            return
        }

        setLoading(true)
        try {
            const response = await fetch(`${BACKEND_API_BASE}/api/auth/change-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: currentEmail,
                    current_password: currentPassword,
                    new_password: newPassword,
                }),
            })
            const data = await response.json().catch(() => ({}))
            if (!response.ok || !data?.success) {
                throw new Error(data?.error || '密码修改失败，请稍后重试。')
            }
            setStatusText('密码修改成功！')
            setStatusType('success')
            setCurrentPassword('')
            setNewPassword('')
            setConfirmPassword('')
        } catch (error) {
            setStatusText(error instanceof Error ? error.message : '密码修改失败，请稍后重试。')
            setStatusType('error')
        } finally {
            setLoading(false)
        }
    }

    const handleLogout = async () => {
        try {
            await fetch('/api/auth/logout', { method: 'POST' })
        } catch {
            // ignore
        }
        window.location.href = '/'
    }

    return (
        <div className="flex min-h-screen bg-[#FAF9F6] dark:bg-[#101217]">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-4xl px-6 py-8">
                    <div className="mb-4">
                        <Link
                            href="/settings"
                            className="inline-flex items-center gap-2 rounded-lg border border-[#E5E5E5] bg-white px-3 py-2 text-sm font-medium text-[#111111] transition hover:bg-[#F5F5F5] dark:border-[#2d3542] dark:bg-[#181c24] dark:text-[#f4f7fb] dark:hover:bg-[#222832]"
                        >
                            <ArrowLeft className="h-4 w-4" />
                            返回设置
                        </Link>
                    </div>

                    <section className="rounded-3xl border border-[#E5E5E5] bg-[#FAF9F6] p-8 shadow-sm dark:border-[#2d3542] dark:bg-[#101217]">
                        <div className="flex items-start gap-4">
                            <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-[#E5E5E5] bg-white dark:border-[#2d3542] dark:bg-[#181c24]">
                                <KeyRound className="h-6 w-6 text-[#111111] dark:text-[#f4f7fb]" />
                            </div>
                            <div>
                                <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#111111] dark:text-[#f4f7fb]">
                                    账号安全
                                </h1>
                                <p className="mt-2 text-sm leading-6 text-[#666666] dark:text-[#bcc5d3]">
                                    修改登录密码或退出当前账号，保护你的账号安全。
                                </p>
                            </div>
                        </div>
                    </section>

                    {/* 修改密码 */}
                    <section className="mt-6 rounded-2xl border border-[#E5E5E5] bg-white p-6 dark:border-[#2d3542] dark:bg-[#181c24]">
                        <h2 className="text-base font-semibold text-[#111111] dark:text-[#f4f7fb]">修改密码</h2>
                        <p className="mt-1 text-sm text-[#666666] dark:text-[#bcc5d3]">
                            修改后需要使用新密码重新登录。
                        </p>

                        <div className="mt-5 space-y-4">
                            {/* 当前密码 */}
                            <div className="space-y-2">
                                <label htmlFor="current-password" className="text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">
                                    当前密码
                                </label>
                                <div className="relative">
                                    <input
                                        id="current-password"
                                        type={showCurrent ? 'text' : 'password'}
                                        autoComplete="current-password"
                                        value={currentPassword}
                                        onChange={(e) => setCurrentPassword(e.target.value)}
                                        placeholder="请输入当前密码"
                                        className="h-11 w-full rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] px-4 pr-11 text-sm text-[#111111] outline-none transition focus:border-[#111111] focus:ring-1 focus:ring-[#111111] dark:border-[#2d3542] dark:bg-[#101217] dark:text-[#f4f7fb] dark:focus:border-[#f4f7fb] dark:focus:ring-[#f4f7fb]"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowCurrent(!showCurrent)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[#999999] hover:text-[#111111] dark:hover:text-[#f4f7fb]"
                                    >
                                        {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                    </button>
                                </div>
                            </div>

                            {/* 新密码 */}
                            <div className="space-y-2">
                                <label htmlFor="new-password" className="text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">
                                    新密码
                                </label>
                                <div className="relative">
                                    <input
                                        id="new-password"
                                        type={showNew ? 'text' : 'password'}
                                        autoComplete="new-password"
                                        value={newPassword}
                                        onChange={(e) => setNewPassword(e.target.value)}
                                        placeholder="请输入至少 8 位新密码"
                                        className="h-11 w-full rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] px-4 pr-11 text-sm text-[#111111] outline-none transition focus:border-[#111111] focus:ring-1 focus:ring-[#111111] dark:border-[#2d3542] dark:bg-[#101217] dark:text-[#f4f7fb] dark:focus:border-[#f4f7fb] dark:focus:ring-[#f4f7fb]"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowNew(!showNew)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[#999999] hover:text-[#111111] dark:hover:text-[#f4f7fb]"
                                    >
                                        {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                    </button>
                                </div>
                            </div>

                            {/* 确认新密码 */}
                            <div className="space-y-2">
                                <label htmlFor="confirm-password" className="text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">
                                    确认新密码
                                </label>
                                <input
                                    id="confirm-password"
                                    type="password"
                                    autoComplete="new-password"
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    placeholder="请再次输入新密码"
                                    className="h-11 w-full rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] px-4 text-sm text-[#111111] outline-none transition focus:border-[#111111] focus:ring-1 focus:ring-[#111111] dark:border-[#2d3542] dark:bg-[#101217] dark:text-[#f4f7fb] dark:focus:border-[#f4f7fb] dark:focus:ring-[#f4f7fb]"
                                />
                            </div>
                        </div>

                        {/* 状态提示 */}
                        {statusText && (
                            <div
                                className={`mt-4 rounded-xl border px-4 py-3 text-sm ${
                                    statusType === 'success'
                                        ? 'border-green-200 bg-green-50 text-green-700 dark:border-green-900 dark:bg-green-950 dark:text-green-300'
                                        : 'border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300'
                                }`}
                            >
                                {statusText}
                            </div>
                        )}

                        <div className="mt-5 flex justify-end">
                            <button
                                type="button"
                                disabled={loading}
                                onClick={handleChangePassword}
                                className="inline-flex items-center gap-2 rounded-xl bg-[#111111] px-5 py-2.5 text-sm font-medium text-white transition hover:bg-[#222222] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-[#f4f7fb] dark:text-[#101217] dark:hover:bg-white"
                            >
                                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                                修改密码
                            </button>
                        </div>
                    </section>

                    {/* 退出登录 */}
                    <section className="mt-4 rounded-2xl border border-[#E5E5E5] bg-white p-6 dark:border-[#2d3542] dark:bg-[#181c24]">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-base font-semibold text-[#111111] dark:text-[#f4f7fb]">退出登录</h2>
                                <p className="mt-1 text-sm text-[#666666] dark:text-[#bcc5d3]">
                                    退出当前账号，返回登录页面。
                                </p>
                            </div>
                            <button
                                type="button"
                                onClick={handleLogout}
                                className="inline-flex items-center gap-2 rounded-xl border border-[#E5E5E5] bg-white px-4 py-2 text-sm font-medium text-[#111111] transition hover:bg-[#F5F5F5] dark:border-[#2d3542] dark:bg-[#181c24] dark:text-[#f4f7fb] dark:hover:bg-[#222832]"
                            >
                                <LogOut className="h-4 w-4" />
                                退出登录
                            </button>
                        </div>
                    </section>
                </div>
            </main>
        </div>
    )
}

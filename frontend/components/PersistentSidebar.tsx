'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { ChangeEvent, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import {
    BarChart3,
    BookOpen,
    Bot,
    Camera,
    ClipboardList,
    Film,
    LayoutDashboard,
    LogOut,
    MessageSquare,
    Network,
    PanelLeftClose,
    PanelLeftOpen,
    Settings,
    X,
} from 'lucide-react'
import LogoutAction from '@/components/LogoutAction'

const SIDEBAR_COLLAPSE_KEY = 'zhiyuexingchen.sidebar.collapsed'
const SIDEBAR_PROFILE_KEY = 'zhiyuexingchen.sidebar.profile'

const MAIN_NAV_ITEMS = [
    { href: '/dashboard', label: '主工作台', icon: LayoutDashboard },
    { href: '/dashboard/questions', label: '题库浏览', icon: BookOpen },
    { href: '/history', label: '面试记录', icon: ClipboardList },
    { href: '/replay', label: '面试复盘', icon: Film },
    { href: '/insights', label: '综合画像', icon: BarChart3 },
    { href: '/knowledge-graph', label: '知识图谱', icon: Network },
    { href: '/assistant', label: 'AI问答助手', icon: Bot },
    { href: '/community', label: '社区', icon: MessageSquare },
]

const BOTTOM_NAV_ITEMS = [{ href: '/settings', label: '设置', icon: Settings }]

type SidebarProfile = {
    nickname: string
    avatarDataUrl: string
    email: string
}

const DEFAULT_PROFILE: SidebarProfile = {
    nickname: '求职者',
    avatarDataUrl: '',
    email: '',
}

function isActive(pathname: string, href: string): boolean {
    if (href === '/dashboard') {
        return pathname === '/dashboard'
    }
    return pathname === href || pathname.startsWith(`${href}/`)
}

function getInitials(nickname: string): string {
    const chars = Array.from(nickname.trim())
    if (chars.length === 0) return 'HS'
    if (chars.length === 1) return chars[0]
    return chars.slice(-2).join('')
}

function readStoredProfile(): Partial<SidebarProfile> | null {
    try {
        const raw = window.localStorage.getItem(SIDEBAR_PROFILE_KEY)
        if (!raw) return null

        const parsed = JSON.parse(raw)
        if (!parsed || typeof parsed !== 'object') return null

        return {
            nickname: typeof parsed.nickname === 'string' ? parsed.nickname : '',
            avatarDataUrl: typeof parsed.avatarDataUrl === 'string' ? parsed.avatarDataUrl : '',
            email: typeof parsed.email === 'string' ? parsed.email : '',
        }
    } catch {
        return null
    }
}

export default function PersistentSidebar() {
    const pathname = usePathname() || ''
    const [collapsed, setCollapsed] = useState(false)
    const [profile, setProfile] = useState<SidebarProfile>(DEFAULT_PROFILE)
    const [profileReady, setProfileReady] = useState(false)
    const [profileEditorOpen, setProfileEditorOpen] = useState(false)
    const [draftProfile, setDraftProfile] = useState<SidebarProfile>(DEFAULT_PROFILE)

    useEffect(() => {
        try {
            const raw = window.localStorage.getItem(SIDEBAR_COLLAPSE_KEY)
            setCollapsed(raw === '1')
        } catch {
            setCollapsed(false)
        }
    }, [])

    useEffect(() => {
        try {
            window.localStorage.setItem(SIDEBAR_COLLAPSE_KEY, collapsed ? '1' : '0')
        } catch {
            // ignore storage failures
        }
    }, [collapsed])

    useEffect(() => {
        const storedProfile = readStoredProfile()
        if (storedProfile) {
            setProfile((prev) => ({
                nickname: storedProfile.nickname?.trim() || prev.nickname,
                avatarDataUrl: storedProfile.avatarDataUrl || '',
                email: storedProfile.email || prev.email,
            }))
        }
        setProfileReady(true)
    }, [])

    useEffect(() => {
        let active = true

        const loadSessionProfile = async () => {
            try {
                const response = await fetch('/api/auth/me', { cache: 'no-store' })
                if (!response.ok) return

                const data = await response.json()
                if (!active || !data?.success) return

                const sessionName =
                    typeof data.user?.name === 'string' && data.user.name.trim()
                        ? data.user.name.trim()
                        : typeof data.user?.email === 'string' && data.user.email.includes('@')
                            ? data.user.email.split('@')[0]
                            : DEFAULT_PROFILE.nickname

                setProfile((prev) => ({
                    nickname: prev.nickname.trim() || sessionName,
                    avatarDataUrl: prev.avatarDataUrl,
                    email: typeof data.user?.email === 'string' ? data.user.email : prev.email,
                }))
            } catch {
                // keep local profile if auth profile is unavailable
            }
        }

        void loadSessionProfile()

        return () => {
            active = false
        }
    }, [])

    useEffect(() => {
        if (!profileReady) return

        try {
            window.localStorage.setItem(SIDEBAR_PROFILE_KEY, JSON.stringify(profile))
        } catch {
            // ignore storage failures
        }
    }, [profile, profileReady])

    const shouldHideSidebar =
        pathname.startsWith('/interview') ||
        pathname.startsWith('/interview-setup') ||
        pathname.startsWith('/liveness')

    if (shouldHideSidebar) {
        return null
    }

    const openProfileEditor = () => {
        setDraftProfile(profile)
        setProfileEditorOpen(true)
    }

    const closeProfileEditor = () => {
        setProfileEditorOpen(false)
    }

    const handleProfileSave = () => {
        const nextNickname = draftProfile.nickname.trim() || profile.email.split('@')[0] || DEFAULT_PROFILE.nickname

        setProfile((prev) => ({
            ...prev,
            nickname: nextNickname,
            avatarDataUrl: draftProfile.avatarDataUrl,
        }))
        setProfileEditorOpen(false)
    }

    if (collapsed) {
        return (
            <div className="hidden w-0 shrink-0 md:block">
                <button
                    type="button"
                    onClick={() => setCollapsed(false)}
                    className="fixed left-3 top-4 z-40 inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[#E5E5E5] bg-white/95 text-[#111111] shadow-sm backdrop-blur transition hover:bg-[#F3F1EB]"
                    title="展开侧边栏"
                    aria-label="展开侧边栏"
                >
                    <PanelLeftOpen className="h-4 w-4" />
                </button>
            </div>
        )
    }

    return (
        <aside className="hidden h-screen w-64 shrink-0 border-r border-[#E5E5E5] bg-[#FAF9F6] md:sticky md:top-0 md:block">
            <div className="flex h-full flex-col">
                <div className="flex h-16 items-center justify-between border-b border-[#E5E5E5] px-4">
                    <Link href="/dashboard" className="text-lg font-serif italic font-medium text-[#111111]">
                        PanelMind
                    </Link>
                    <button
                        type="button"
                        onClick={() => setCollapsed(true)}
                        className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[#E5E5E5] bg-white text-[#666666] transition hover:bg-[#F1F0EC] hover:text-[#111111]"
                        title="收起侧边栏"
                        aria-label="收起侧边栏"
                    >
                        <PanelLeftClose className="h-4 w-4" />
                    </button>
                </div>

                <nav className="flex-1 space-y-1 overflow-y-auto px-4 py-6">
                    {MAIN_NAV_ITEMS.map((item) => {
                        const Icon = item.icon
                        const active = isActive(pathname, item.href)
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                aria-current={active ? 'page' : undefined}
                                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                                    active
                                        ? 'bg-[#EBE9E0] text-[#111111]'
                                        : 'text-[#666666] hover:bg-[#F1F0EC] hover:text-[#111111]'
                                }`}
                            >
                                <Icon className="h-4 w-4 shrink-0" />
                                <span>{item.label}</span>
                            </Link>
                        )
                    })}
                </nav>

                <div className="px-4 pb-3">
                    <div className="space-y-1">
                        {BOTTOM_NAV_ITEMS.map((item) => {
                            const Icon = item.icon
                            const active = isActive(pathname, item.href)
                            return (
                                <Link
                                    key={item.href}
                                    href={item.href}
                                    aria-current={active ? 'page' : undefined}
                                    className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                                        active
                                            ? 'bg-[#EBE9E0] text-[#111111]'
                                            : 'text-[#666666] hover:bg-[#F1F0EC] hover:text-[#111111]'
                                    }`}
                                >
                                    <Icon className="h-4 w-4 shrink-0" />
                                    <span>{item.label}</span>
                                </Link>
                            )
                        })}

                        <LogoutAction className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-[#666666] transition-colors hover:bg-[#F1F0EC] hover:text-[#111111]">
                            <LogOut className="h-4 w-4 shrink-0" />
                            <span>退出登录</span>
                        </LogoutAction>
                    </div>
                </div>

                <div className="mt-auto border-t border-[#E5E5E5] px-4 py-5">
                    <button
                        type="button"
                        onClick={openProfileEditor}
                        className="mx-auto flex w-full flex-col items-center justify-center gap-2 text-center transition hover:opacity-85"
                    >
                        <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-full bg-[#ECE7DB] text-lg font-semibold text-[#6B5E49]">
                            {profile.avatarDataUrl ? (
                                <img src={profile.avatarDataUrl} alt={`${profile.nickname} 的头像`} className="h-full w-full object-cover" />
                            ) : (
                                <span>{getInitials(profile.nickname)}</span>
                            )}
                        </div>
                        <p className="max-w-full truncate text-sm font-medium text-[#111111]">{profile.nickname}</p>
                    </button>
                </div>
            </div>

            {profileEditorOpen ? (
                <ProfileEditorModal
                    profile={profile}
                    draftProfile={draftProfile}
                    setDraftProfile={setDraftProfile}
                    onClose={closeProfileEditor}
                    onSave={handleProfileSave}
                />
            ) : null}
        </aside>
    )
}

function ProfileEditorModal({
    profile,
    draftProfile,
    setDraftProfile,
    onClose,
    onSave,
}: {
    profile: SidebarProfile
    draftProfile: SidebarProfile
    setDraftProfile: React.Dispatch<React.SetStateAction<SidebarProfile>>
    onClose: () => void
    onSave: () => void
}) {
    const [mounted, setMounted] = useState(false)

    useEffect(() => {
        setMounted(true)
    }, [])

    const handleAvatarChange = (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        event.target.value = ''

        if (!file || !file.type.startsWith('image/')) return

        const reader = new FileReader()
        reader.onload = () => {
            const result = reader.result
            if (typeof result !== 'string') return
            setDraftProfile((prev) => ({ ...prev, avatarDataUrl: result }))
        }
        reader.readAsDataURL(file)
    }

    if (!mounted) return null

    return createPortal(
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[rgba(17,17,17,0.28)] p-6" onClick={onClose}>
            <div
                className="w-full max-w-xl rounded-[32px] bg-[#FAF9F6] p-7 shadow-[0_24px_72px_rgba(17,17,17,0.24)]"
                onClick={(event) => event.stopPropagation()}
            >
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <p className="text-2xl font-semibold text-[#111111]">编辑个人信息</p>
                        <p className="mt-2 text-sm leading-6 text-[#6E675D]">在这里设置你的头像和昵称</p>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="inline-flex h-10 w-10 items-center justify-center rounded-full text-[#666666] transition hover:bg-[#F0ECE3] hover:text-[#111111]"
                        aria-label="关闭个人信息弹窗"
                    >
                        <X className="h-5 w-5" />
                    </button>
                </div>

                <div className="mt-8 grid gap-6 md:grid-cols-[160px_minmax(0,1fr)] md:items-start">
                    <div className="flex flex-col items-center text-center">
                        <div className="flex h-32 w-32 items-center justify-center overflow-hidden rounded-full bg-[#ECE7DB] text-3xl font-semibold text-[#6B5E49]">
                            {draftProfile.avatarDataUrl ? (
                                <img src={draftProfile.avatarDataUrl} alt="头像预览" className="h-full w-full object-cover" />
                            ) : (
                                <span>{getInitials(draftProfile.nickname)}</span>
                            )}
                        </div>
                        <label className="mt-4 inline-flex cursor-pointer items-center gap-2 rounded-xl bg-[#111111] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-[#2A2A2A]">
                            <Camera className="h-4 w-4" />
                            <span>上传头像</span>
                            <input type="file" accept="image/*" className="hidden" onChange={handleAvatarChange} />
                        </label>
                        <button
                            type="button"
                            onClick={() => setDraftProfile((prev) => ({ ...prev, avatarDataUrl: '' }))}
                            className="mt-3 text-sm text-[#8A7350] transition hover:text-[#5C4A33]"
                        >
                            移除头像
                        </button>
                    </div>

                    <div className="space-y-5">
                        <label className="block text-sm text-[#3E3831]">
                            <span className="mb-2 block font-medium">昵称</span>
                            <input
                                value={draftProfile.nickname}
                                onChange={(event) => setDraftProfile((prev) => ({ ...prev, nickname: event.target.value }))}
                                placeholder="请输入昵称"
                                className="w-full rounded-2xl border border-[#DED7CB] bg-white px-4 py-3 text-[#111111] outline-none transition focus:border-[#9A8767]"
                            />
                        </label>

                        <div className="rounded-2xl bg-[#F3EFE6] px-4 py-3 text-sm leading-6 text-[#6E675D]">
                            保存后会同步更新左侧头像和昵称展示。
                        </div>
                    </div>
                </div>

                <div className="mt-8 flex items-center justify-end gap-3">
                    <button
                        type="button"
                        onClick={onClose}
                        className="rounded-xl px-4 py-2.5 text-sm text-[#6C655C] transition hover:bg-[#F0ECE3] hover:text-[#111111]"
                    >
                        取消
                    </button>
                    <button
                        type="button"
                        onClick={onSave}
                        className="rounded-xl bg-[#111111] px-5 py-2.5 text-sm font-medium text-white transition hover:bg-[#2A2A2A]"
                    >
                        保存
                    </button>
                </div>
            </div>
        </div>,
        document.body
    )
}

'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
    ArrowLeft,
    Check,
    LogOut,
    Users,
} from 'lucide-react'
import { motion } from 'motion/react'
import {
    getGroupById,
    joinGroup,
    leaveGroup,
    isGroupMember,
    type StudyGroup,
} from '@/lib/community'

function formatTime(ts: number): string {
    const d = new Date(ts)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function GroupDetailPage() {
    const params = useParams()
    const groupId = String(params.id || '')
    const [group, setGroup] = useState<StudyGroup | null>(null)
    const [isMember, setIsMember] = useState(false)
    const [nickname, setNickname] = useState('')
    const [version, setVersion] = useState(0)

    useEffect(() => {
        const stored = localStorage.getItem('zhiyuexingchen.sidebar.profile')
        if (stored) {
            try {
                const parsed = JSON.parse(stored)
                if (parsed?.nickname) setNickname(parsed.nickname)
            } catch {
                // ignore
            }
        }
    }, [])

    useEffect(() => {
        if (!groupId) return
        const g = getGroupById(groupId)
        if (g) {
            setGroup(g)
            const name = nickname.trim() || '匿名用户'
            setIsMember(isGroupMember(groupId, name))
        }
    }, [groupId, nickname, version])

    const handleJoin = () => {
        if (!groupId) return
        const name = nickname.trim() || '匿名用户'
        const result = joinGroup(groupId, name)
        if (result) {
            setIsMember(true)
            setGroup(getGroupById(groupId) || null)
            setVersion((v) => v + 1)
        }
    }

    const handleLeave = () => {
        if (!groupId) return
        const name = nickname.trim() || '匿名用户'
        leaveGroup(groupId, name)
        setIsMember(false)
        setGroup(getGroupById(groupId) || null)
        setVersion((v) => v + 1)
    }

    if (!group) {
        return (
            <div className="flex-1 min-h-0 overflow-y-auto p-8 lg:p-12">
                <div className="max-w-3xl mx-auto text-center py-20 text-[var(--ink-muted)]">
                    <p>小组不存在或已被删除。</p>
                    <Link href="/community" className="mt-4 inline-block text-sm text-[var(--ink)] hover:underline">
                        返回社区
                    </Link>
                </div>
            </div>
        )
    }

    const progress = Math.round((group.memberCount / group.maxMembers) * 100)

    return (
        <div className="flex-1 min-h-0 overflow-y-auto p-8 lg:p-12">
            <div className="max-w-3xl mx-auto space-y-8">
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                    <Link
                        href="/community"
                        className="inline-flex items-center gap-1 text-sm text-[var(--ink-muted)] hover:text-[var(--ink)] transition"
                    >
                        <ArrowLeft size={14} />
                        返回社区
                    </Link>
                </motion.div>

                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
                    <Card className="p-6">
                        <div className="flex items-start justify-between gap-4">
                            <div className="flex items-start gap-4">
                                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-[#EBE9E0] text-2xl dark:bg-[#2d3542]">
                                    {group.name.slice(0, 1)}
                                </div>
                                <div>
                                    <h1 className="text-xl font-semibold text-[var(--ink)]">{group.name}</h1>
                                    <p className="mt-1 text-sm text-[var(--ink-muted)]">{group.description}</p>
                                    <div className="mt-3 flex items-center gap-2 flex-wrap">
                                        {group.tags.map((tag) => (
                                            <span
                                                key={tag}
                                                className="rounded-full bg-[var(--accent)] px-2.5 py-0.5 text-xs text-[var(--ink-muted)]"
                                            >
                                                {tag}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            </div>
                            {isMember ? (
                                <Button variant="outline" size="sm" onClick={handleLeave} className="gap-1.5 shrink-0">
                                    <LogOut size={14} />
                                    退出小组
                                </Button>
                            ) : (
                                <Button size="sm" onClick={handleJoin} className="gap-1.5 shrink-0">
                                    <Check size={14} />
                                    加入小组
                                </Button>
                            )}
                        </div>

                        <div className="mt-6 grid grid-cols-3 gap-4 border-t border-[var(--border)] pt-5">
                            <div className="text-center">
                                <div className="text-lg font-semibold text-[var(--ink)]">{group.memberCount}</div>
                                <div className="text-xs text-[var(--ink-lighter)]">成员</div>
                            </div>
                            <div className="text-center">
                                <div className="text-lg font-semibold text-[var(--ink)]">{group.maxMembers}</div>
                                <div className="text-xs text-[var(--ink-lighter)]">上限</div>
                            </div>
                            <div className="text-center">
                                <div className="text-lg font-semibold text-[var(--ink)]">{formatTime(group.createdAt)}</div>
                                <div className="text-xs text-[var(--ink-lighter)]">创建时间</div>
                            </div>
                        </div>

                        {/* Progress bar */}
                        <div className="mt-5">
                            <div className="flex items-center justify-between text-xs text-[var(--ink-lighter)] mb-1.5">
                                <span className="inline-flex items-center gap-1">
                                    <Users size={12} />
                                    人数进度
                                </span>
                                <span>{progress}%</span>
                            </div>
                            <div className="h-2 w-full rounded-full bg-[var(--accent)] overflow-hidden">
                                <div
                                    className="h-full rounded-full bg-[#111111] transition-all duration-500"
                                    style={{ width: `${progress}%` }}
                                />
                            </div>
                        </div>

                        {isMember && (
                            <div className="mt-5 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-300">
                                你已经是小组成员了！可以在组内与其他成员交流学习。
                            </div>
                        )}
                    </Card>
                </motion.div>

                {/* Members */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.2 }}
                    className="space-y-4"
                >
                    <h2 className="text-lg font-semibold text-[var(--ink)]">小组成员</h2>
                    {group.members.length === 0 ? (
                        <p className="text-sm text-[var(--ink-muted)]">暂无成员信息。</p>
                    ) : (
                        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                            {group.members.map((member, i) => (
                                <Card key={`${member}_${i}`} className="p-3 flex items-center gap-2">
                                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#EBE9E0] text-xs font-semibold text-[#6B5E49] dark:bg-[#2d3542] dark:text-[#D6C7A6]">
                                        {member.slice(0, 2)}
                                    </div>
                                    <span className="text-sm text-[var(--ink)] truncate">{member}</span>
                                </Card>
                            ))}
                        </div>
                    )}
                </motion.div>
            </div>
        </div>
    )
}

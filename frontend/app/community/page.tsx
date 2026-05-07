'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
    Heart,
    MessageCircle,
    Plus,
    Search,
    ShieldCheck,
    Users,
} from 'lucide-react'
import { motion } from 'motion/react'
import {
    getPosts,
    getGroups,
    likePost,
    hasLikedPost,
    seedDemoPosts,
    type PostItem,
    type StudyGroup,
} from '@/lib/community'

function formatTime(ts: number): string {
    const now = Date.now()
    const diff = now - ts
    const minutes = Math.floor(diff / (1000 * 60))
    const hours = Math.floor(diff / (1000 * 60 * 60))
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    if (minutes < 1) return '刚刚'
    if (minutes < 60) return `${minutes}分钟前`
    if (hours < 24) return `${hours}小时前`
    if (days < 30) return `${days}天前`
    const d = new Date(ts)
    return `${d.getMonth() + 1}月${d.getDate()}日`
}

const TABS = [
    { key: 'posts' as const, label: '面经广场' },
    { key: 'groups' as const, label: '学习小组' },
]

export default function CommunityPage() {
    const [activeTab, setActiveTab] = useState<'posts' | 'groups'>('posts')
    const [posts, setPosts] = useState<PostItem[]>([])
    const [groups, setGroups] = useState<StudyGroup[]>([])
    const [searchQuery, setSearchQuery] = useState('')
    const [version, setVersion] = useState(0)

    useEffect(() => {
        seedDemoPosts()
        setPosts(getPosts())
        setGroups(getGroups())
    }, [])

    const filteredPosts = useMemo(() => {
        if (!searchQuery.trim()) return posts
        const q = searchQuery.toLowerCase()
        return posts.filter(
            (p) =>
                p.title.toLowerCase().includes(q) ||
                p.content.toLowerCase().includes(q) ||
                p.tags.some((t) => t.toLowerCase().includes(q))
        )
    }, [posts, searchQuery])

    const filteredGroups = useMemo(() => {
        if (!searchQuery.trim()) return groups
        const q = searchQuery.toLowerCase()
        return groups.filter(
            (g) =>
                g.name.toLowerCase().includes(q) ||
                g.description.toLowerCase().includes(q) ||
                g.tags.some((t) => t.toLowerCase().includes(q))
        )
    }, [groups, searchQuery])

    const handleLike = useCallback((postId: string) => {
        likePost(postId)
        setPosts(getPosts())
        setVersion((v) => v + 1)
    }, [])

    return (
        <div className="flex-1 min-h-0 overflow-y-auto p-8 lg:p-12">
            <div className="max-w-5xl mx-auto space-y-8">
                <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                        <h1 className="text-3xl font-serif text-[var(--ink)] tracking-tight">社区</h1>
                        <p className="text-[var(--ink-muted)] mt-2">分享面经、交流心得、组队学习。</p>
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 }}
                        className="flex items-center gap-3"
                    >
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ink-lighter)]" size={16} />
                            <input
                                type="text"
                                placeholder="搜索帖子或小组..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="h-10 pl-9 pr-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm focus:outline-none focus:border-[var(--ink)] focus:ring-1 focus:ring-[var(--ink)] transition-all w-full md:w-64"
                            />
                        </div>
                        <Link
                            href="/community/post"
                            className="inline-flex items-center gap-2 rounded-lg bg-[#111111] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#2A2A2A]"
                        >
                            <Plus size={16} />
                            发布帖子
                        </Link>
                    </motion.div>
                </header>

                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.2 }}
                    className="flex gap-2"
                >
                    {TABS.map((tab) => (
                        <button
                            key={tab.key}
                            onClick={() => setActiveTab(tab.key)}
                            className={`px-5 py-2.5 text-sm font-medium rounded-full border transition-all duration-200 ${
                                activeTab === tab.key
                                    ? 'bg-[#111111] text-white border-[#111111]'
                                    : 'bg-[var(--surface)] text-[var(--ink-muted)] border-[var(--border)] hover:bg-[var(--accent)] hover:text-[var(--ink)]'
                            }`}
                        >
                            {tab.label}
                        </button>
                    ))}
                </motion.div>

                {activeTab === 'posts' ? (
                    <div className="space-y-4">
                        {filteredPosts.length === 0 ? (
                            <div className="py-16 text-center text-[var(--ink-muted)]">
                                <MessageCircle className="mx-auto mb-3 h-10 w-10 opacity-40" />
                                <p>暂无帖子，来做第一个分享的人吧。</p>
                            </div>
                        ) : (
                            filteredPosts.map((post, index) => (
                                <motion.div
                                    key={post.id}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: index * 0.03 }}
                                >
                                    <Link href={`/community/post/${post.id}`}>
                                        <Card className="p-5 hover:border-[var(--ink)] transition-all cursor-pointer">
                                            <div className="flex items-start gap-4">
                                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#EBE9E0] text-sm font-semibold text-[#6B5E49] dark:bg-[#2d3542] dark:text-[#D6C7A6]">
                                                    {post.author.slice(0, 2)}
                                                </div>
                                                <div className="min-w-0 flex-1">
                                                    <div className="flex items-center gap-2 flex-wrap">
                                                        <span className="text-sm font-medium text-[var(--ink)]">{post.author}</span>
                                                        {post.isOfficial && (
                                                            <span className="inline-flex items-center gap-1 rounded-full bg-[#F3F1EB] px-2 py-0.5 text-[10px] font-medium text-[#8B6F3D] dark:bg-[#2d3542] dark:text-[#D6C7A6]">
                                                                <ShieldCheck size={10} />
                                                                官方推荐
                                                            </span>
                                                        )}
                                                        <span className="text-xs text-[var(--ink-lighter)]">{formatTime(post.createdAt)}</span>
                                                    </div>
                                                    <h3 className="mt-1.5 text-base font-semibold text-[var(--ink)] leading-snug">{post.title}</h3>
                                                    <p className="mt-1.5 text-sm text-[var(--ink-muted)] line-clamp-2 leading-relaxed">
                                                        {post.content.replace(/\n/g, ' ')}
                                                    </p>
                                                    <div className="mt-3 flex items-center gap-3">
                                                        <div className="flex flex-wrap gap-1.5">
                                                            {post.tags.map((tag) => (
                                                                <span
                                                                    key={tag}
                                                                    className="rounded-full bg-[var(--accent)] px-2.5 py-0.5 text-xs text-[var(--ink-muted)]"
                                                                >
                                                                    {tag}
                                                                </span>
                                                            ))}
                                                        </div>
                                                        <div className="ml-auto flex items-center gap-4 text-xs text-[var(--ink-lighter)]">
                                                            <button
                                                                type="button"
                                                                onClick={(e) => {
                                                                    e.preventDefault()
                                                                    e.stopPropagation()
                                                                    handleLike(post.id)
                                                                }}
                                                                className={`inline-flex items-center gap-1 transition ${
                                                                    hasLikedPost(post.id)
                                                                        ? 'text-red-500'
                                                                        : 'hover:text-red-500'
                                                                }`}
                                                            >
                                                                <Heart size={14} className={hasLikedPost(post.id) ? 'fill-current' : ''} />
                                                                {post.likes}
                                                            </button>
                                                            <span className="inline-flex items-center gap-1">
                                                                <MessageCircle size={14} />
                                                                {post.comments}
                                                            </span>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </Card>
                                    </Link>
                                </motion.div>
                            ))
                        )}
                    </div>
                ) : (
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <p className="text-sm text-[var(--ink-muted)]">共 {filteredGroups.length} 个学习小组</p>
                            <Link
                                href="/community/group/create"
                                className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--ink)] hover:underline"
                            >
                                <Plus size={14} />
                                创建小组
                            </Link>
                        </div>
                        {filteredGroups.length === 0 ? (
                            <div className="py-16 text-center text-[var(--ink-muted)]">
                                <Users className="mx-auto mb-3 h-10 w-10 opacity-40" />
                                <p>暂无学习小组，来创建第一个吧。</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {filteredGroups.map((group, index) => (
                                    <motion.div
                                        key={group.id}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: index * 0.03 }}
                                    >
                                        <Link href={`/community/group/${group.id}`}>
                                            <Card className="p-5 hover:border-[var(--ink)] transition-all cursor-pointer h-full">
                                                <div className="flex items-start justify-between gap-3">
                                                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#EBE9E0] text-lg dark:bg-[#2d3542]">
                                                        {group.name.slice(0, 1)}
                                                    </div>
                                                    <div className="min-w-0 flex-1">
                                                        <h3 className="text-base font-semibold text-[var(--ink)]">{group.name}</h3>
                                                        <p className="mt-1 text-sm text-[var(--ink-muted)] line-clamp-2">{group.description}</p>
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
                                                        <div className="mt-3 flex items-center gap-4 text-xs text-[var(--ink-lighter)]">
                                                            <span className="inline-flex items-center gap-1">
                                                                <Users size={12} />
                                                                {group.memberCount} / {group.maxMembers} 人
                                                            </span>
                                                            <span>创建于 {formatTime(group.createdAt)}</span>
                                                        </div>
                                                    </div>
                                                </div>
                                            </Card>
                                        </Link>
                                    </motion.div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    )
}

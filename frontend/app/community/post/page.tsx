'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { ArrowLeft, Plus, X } from 'lucide-react'
import { motion } from 'motion/react'
import { addPost } from '@/lib/community'

export default function CreatePostPage() {
    const router = useRouter()
    const [title, setTitle] = useState('')
    const [content, setContent] = useState('')
    const [tags, setTags] = useState<string[]>([])
    const [tagInput, setTagInput] = useState('')
    const [nickname, setNickname] = useState('')
    const [submitting, setSubmitting] = useState(false)

    const handleAddTag = () => {
        const text = tagInput.trim()
        if (!text || tags.includes(text)) return
        setTags([...tags, text])
        setTagInput('')
    }

    const handleRemoveTag = (tag: string) => {
        setTags(tags.filter((t) => t !== tag))
    }

    const handleSubmit = () => {
        if (!title.trim() || !content.trim()) return
        setSubmitting(true)
        const author = nickname.trim() || '匿名用户'
        addPost(author, '', title.trim(), content.trim(), tags)
        router.push('/community')
    }

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
                    <h1 className="mt-3 text-3xl font-serif text-[var(--ink)] tracking-tight">发布帖子</h1>
                    <p className="text-[var(--ink-muted)] mt-2">分享你的面经、复盘心得或学习笔记。</p>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.1 }}
                    className="space-y-5"
                >
                    <div>
                        <label className="block text-sm font-medium text-[var(--ink)] mb-2">标题</label>
                        <input
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="给你的帖子起个标题..."
                            className="w-full h-11 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 text-sm focus:outline-none focus:border-[var(--ink)] focus:ring-1 focus:ring-[var(--ink)] transition-all"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-[var(--ink)] mb-2">内容</label>
                        <textarea
                            value={content}
                            onChange={(e) => setContent(e.target.value)}
                            placeholder="写下你想分享的内容...\n支持换行，可以详细描述你的面试经历、技术心得等。"
                            className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm focus:outline-none focus:border-[var(--ink)] focus:ring-1 focus:ring-[var(--ink)] transition-all resize-none"
                            rows={12}
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-[var(--ink)] mb-2">标签</label>
                        <div className="flex flex-wrap items-center gap-2">
                            {tags.map((tag) => (
                                <span
                                    key={tag}
                                    className="inline-flex items-center gap-1 rounded-full bg-[var(--accent)] px-3 py-1 text-xs text-[var(--ink-muted)]"
                                >
                                    {tag}
                                    <button type="button" onClick={() => handleRemoveTag(tag)}>
                                        <X size={12} />
                                    </button>
                                </span>
                            ))}
                            <div className="flex items-center gap-1">
                                <input
                                    value={tagInput}
                                    onChange={(e) => setTagInput(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') {
                                            e.preventDefault()
                                            handleAddTag()
                                        }
                                    }}
                                    placeholder="添加标签"
                                    className="h-8 w-24 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2 text-xs focus:outline-none focus:border-[var(--ink)]"
                                />
                                <button
                                    type="button"
                                    onClick={handleAddTag}
                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--ink-muted)] hover:bg-[var(--accent)] hover:text-[var(--ink)] transition"
                                >
                                    <Plus size={14} />
                                </button>
                            </div>
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-[var(--ink)] mb-2">昵称</label>
                        <input
                            value={nickname}
                            onChange={(e) => setNickname(e.target.value)}
                            placeholder="你的昵称（留空则显示匿名用户）"
                            className="w-full h-10 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 text-sm focus:outline-none focus:border-[var(--ink)] focus:ring-1 focus:ring-[var(--ink)] transition-all"
                        />
                    </div>

                    <div className="flex items-center justify-end gap-3 pt-4">
                        <Link
                            href="/community"
                            className="rounded-xl px-5 py-2.5 text-sm text-[var(--ink-muted)] transition hover:bg-[var(--accent)] hover:text-[var(--ink)]"
                        >
                            取消
                        </Link>
                        <Button
                            onClick={handleSubmit}
                            disabled={!title.trim() || !content.trim() || submitting}
                            className="px-6"
                        >
                            {submitting ? '发布中...' : '发布帖子'}
                        </Button>
                    </div>
                </motion.div>
            </div>
        </div>
    )
}

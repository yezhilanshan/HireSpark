'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { ArrowLeft, Plus, X } from 'lucide-react'
import { motion } from 'motion/react'
import { createGroup } from '@/lib/community'

export default function CreateGroupPage() {
    const router = useRouter()
    const [name, setName] = useState('')
    const [description, setDescription] = useState('')
    const [tags, setTags] = useState<string[]>([])
    const [tagInput, setTagInput] = useState('')
    const [maxMembers, setMaxMembers] = useState(50)
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
        if (!name.trim() || !description.trim()) return
        setSubmitting(true)
        const author = nickname.trim() || '匿名用户'
        createGroup(name.trim(), description.trim(), tags, maxMembers, author)
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
                    <h1 className="mt-3 text-3xl font-serif text-[var(--ink)] tracking-tight">创建学习小组</h1>
                    <p className="text-[var(--ink-muted)] mt-2">组建一个学习小组，和志同道合的伙伴一起进步。</p>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.1 }}
                    className="space-y-5"
                >
                    <div>
                        <label className="block text-sm font-medium text-[var(--ink)] mb-2">小组名称</label>
                        <input
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="给你的小组起个名字..."
                            className="w-full h-11 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 text-sm focus:outline-none focus:border-[var(--ink)] focus:ring-1 focus:ring-[var(--ink)] transition-all"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-[var(--ink)] mb-2">小组介绍</label>
                        <textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="介绍你们小组的学习目标和计划..."
                            className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm focus:outline-none focus:border-[var(--ink)] focus:ring-1 focus:ring-[var(--ink)] transition-all resize-none"
                            rows={5}
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
                        <label className="block text-sm font-medium text-[var(--ink)] mb-2">人数上限</label>
                        <div className="flex items-center gap-4">
                            <input
                                type="range"
                                min={5}
                                max={500}
                                step={5}
                                value={maxMembers}
                                onChange={(e) => setMaxMembers(Number(e.target.value))}
                                className="flex-1"
                            />
                            <span className="w-16 text-right text-sm font-medium text-[var(--ink)]">{maxMembers} 人</span>
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-[var(--ink)] mb-2">你的昵称</label>
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
                            disabled={!name.trim() || !description.trim() || submitting}
                            className="px-6"
                        >
                            {submitting ? '创建中...' : '创建小组'}
                        </Button>
                    </div>
                </motion.div>
            </div>
        </div>
    )
}

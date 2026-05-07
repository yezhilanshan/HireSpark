'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
    ArrowLeft,
    Heart,
    MessageCircle,
    Send,
    ShieldCheck,
} from 'lucide-react'
import { motion } from 'motion/react'
import {
    getPostById,
    getCommentsForPost,
    addComment,
    likePost,
    hasLikedPost,
    type PostItem,
    type CommentItem,
} from '@/lib/community'

function formatTime(ts: number): string {
    const d = new Date(ts)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export default function PostDetailPage() {
    const params = useParams()
    const postId = String(params.id || '')
    const [post, setPost] = useState<PostItem | null>(null)
    const [comments, setComments] = useState<CommentItem[]>([])
    const [commentText, setCommentText] = useState('')
    const [nickname, setNickname] = useState('')
    const [liked, setLiked] = useState(false)
    const [version, setVersion] = useState(0)

    useEffect(() => {
        const stored = localStorage.getItem('hirespark.sidebar.profile')
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
        if (!postId) return
        const p = getPostById(postId)
        if (p) {
            setPost(p)
            setLiked(hasLikedPost(postId))
        }
        setComments(getCommentsForPost(postId))
    }, [postId, version])

    const handleLike = () => {
        if (!postId) return
        const result = likePost(postId)
        setLiked(result)
        const p = getPostById(postId)
        if (p) setPost(p)
        setVersion((v) => v + 1)
    }

    const handleComment = () => {
        const text = commentText.trim()
        if (!text || !postId) return
        const author = nickname.trim() || '匿名用户'
        addComment(postId, author, '', text)
        setComments(getCommentsForPost(postId))
        setCommentText('')
        const p = getPostById(postId)
        if (p) setPost(p)
    }

    if (!post) {
        return (
            <div className="flex-1 min-h-0 overflow-y-auto p-8 lg:p-12">
                <div className="max-w-3xl mx-auto text-center py-20 text-[var(--ink-muted)]">
                    <p>帖子不存在或已被删除。</p>
                    <Link href="/community" className="mt-4 inline-block text-sm text-[var(--ink)] hover:underline">
                        返回社区
                    </Link>
                </div>
            </div>
        )
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
                </motion.div>

                {/* Post */}
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
                    <Card className="p-6">
                        <div className="flex items-center gap-3">
                            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#EBE9E0] text-sm font-semibold text-[#6B5E49] dark:bg-[#2d3542] dark:text-[#D6C7A6]">
                                {post.author.slice(0, 2)}
                            </div>
                            <div>
                                <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-[var(--ink)]">{post.author}</span>
                                    {post.isOfficial && (
                                        <span className="inline-flex items-center gap-1 rounded-full bg-[#F3F1EB] px-2 py-0.5 text-[10px] font-medium text-[#8B6F3D] dark:bg-[#2d3542] dark:text-[#D6C7A6]">
                                            <ShieldCheck size={10} />
                                            官方推荐
                                        </span>
                                    )}
                                </div>
                                <div className="text-xs text-[var(--ink-lighter)]">{formatTime(post.createdAt)}</div>
                            </div>
                        </div>

                        <h1 className="mt-5 text-2xl font-semibold text-[var(--ink)] leading-snug">{post.title}</h1>

                        <div className="mt-4 text-sm text-[var(--ink-muted)] leading-7 whitespace-pre-wrap">
                            {post.content}
                        </div>

                        <div className="mt-5 flex flex-wrap gap-2">
                            {post.tags.map((tag) => (
                                <span
                                    key={tag}
                                    className="rounded-full bg-[var(--accent)] px-3 py-1 text-xs text-[var(--ink-muted)]"
                                >
                                    {tag}
                                </span>
                            ))}
                        </div>

                        <div className="mt-6 flex items-center gap-4 pt-4 border-t border-[var(--border)]">
                            <button
                                type="button"
                                onClick={handleLike}
                                className={`inline-flex items-center gap-1.5 text-sm transition ${
                                    liked ? 'text-red-500' : 'text-[var(--ink-muted)] hover:text-red-500'
                                }`}
                            >
                                <Heart size={16} className={liked ? 'fill-current' : ''} />
                                {post.likes}
                            </button>
                            <span className="inline-flex items-center gap-1.5 text-sm text-[var(--ink-muted)]">
                                <MessageCircle size={16} />
                                {post.comments}
                            </span>
                        </div>
                    </Card>
                </motion.div>

                {/* Comments */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.2 }}
                    className="space-y-4"
                >
                    <h2 className="text-lg font-semibold text-[var(--ink)]">评论 ({comments.length})</h2>

                    <Card className="p-4">
                        <div className="text-sm font-medium text-[var(--ink)]">发表评论</div>
                        <textarea
                            value={commentText}
                            onChange={(e) => setCommentText(e.target.value)}
                            placeholder="写下你的想法..."
                            className="mt-3 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm focus:outline-none focus:border-[var(--ink)] focus:ring-1 focus:ring-[var(--ink)] transition-all resize-none"
                            rows={3}
                        />
                        <div className="mt-3 flex items-center justify-between">
                            <input
                                value={nickname}
                                onChange={(e) => setNickname(e.target.value)}
                                placeholder="你的昵称"
                                className="h-9 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 text-sm focus:outline-none focus:border-[var(--ink)]"
                            />
                            <Button
                                size="sm"
                                disabled={!commentText.trim()}
                                onClick={handleComment}
                                className="gap-1.5"
                            >
                                <Send className="h-3.5 w-3.5" />
                                发送
                            </Button>
                        </div>
                    </Card>

                    {comments.length === 0 ? (
                        <div className="py-8 text-center text-sm text-[var(--ink-muted)]">
                            暂无评论，来做第一个评论的人吧。
                        </div>
                    ) : (
                        comments.map((comment) => (
                            <Card key={comment.id} className="p-4">
                                <div className="flex items-center gap-2">
                                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#EBE9E0] text-xs font-semibold text-[#6B5E49] dark:bg-[#2d3542] dark:text-[#D6C7A6]">
                                        {comment.author.slice(0, 2)}
                                    </div>
                                    <div>
                                        <span className="text-sm font-medium text-[var(--ink)]">{comment.author}</span>
                                        <span className="ml-2 text-xs text-[var(--ink-lighter)]">{formatTime(comment.createdAt)}</span>
                                    </div>
                                </div>
                                <p className="mt-2 text-sm text-[var(--ink-muted)] leading-6">{comment.content}</p>
                            </Card>
                        ))
                    )}
                </motion.div>
            </div>
        </div>
    )
}

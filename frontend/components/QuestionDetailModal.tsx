'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
    Bookmark,
    BookmarkCheck,
    BookOpen,
    Heart,
    MessageCircle,
    Play,
    Send,
    ShieldCheck,
    Star,
    ThumbsUp,
    X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
    addDiscussion,
    getBookmarkTypesForQuestion,
    getDiscussionsForQuestion,
    isBookmarked,
    likeDiscussion,
    toggleBookmark,
    type BookMarkType,
    type DiscussionItem,
} from '@/lib/question-book'

type QuestionDetail = {
    id: string
    uiKey: string
    title: string
    category: string
    categoryKey: string
    positionKey: string
    positionLabel: string
    difficulty: 'Easy' | 'Medium' | 'Hard'
    difficultyKey: 'easy' | 'medium' | 'hard'
    roundType: 'technical' | 'project' | 'system_design' | 'hr'
    sourcePositionKey: string
    frequency: string
}

type Props = {
    question: QuestionDetail | null
    onClose: () => void
    onPractice: (question: QuestionDetail) => void
}

const OFFICIAL_ANSWERS: Record<string, string> = {
    default:
        '这道题考察的是候选人对核心概念的理解深度。建议从原理层面出发，结合实际项目经验作答。回答时应包含：1) 核心概念解释；2) 实际应用场景；3) 优缺点分析；4) 与其他方案的对比。',
}

function formatTime(ts: number): string {
    const d = new Date(ts)
    return `${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function getOfficialAnswer(categoryKey: string): string {
    return (
        OFFICIAL_ANSWERS[categoryKey] ||
        OFFICIAL_ANSWERS.default
    )
}

export default function QuestionDetailModal({ question, onClose, onPractice }: Props) {
    const [activeTab, setActiveTab] = useState<'overview' | 'discussion'>('overview')
    const [bookmarks, setBookmarks] = useState<BookMarkType[]>([])
    const [discussions, setDiscussions] = useState<DiscussionItem[]>([])
    const [newComment, setNewComment] = useState('')
    const [nickname, setNickname] = useState('')
    const scrollRef = useRef<HTMLDivElement>(null)

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
        if (!question) return
        setBookmarks(getBookmarkTypesForQuestion(question.id))
        setDiscussions(getDiscussionsForQuestion(question.id))
        setActiveTab('overview')
        setNewComment('')
    }, [question?.id])

    const officialAnswer = useMemo(
        () => (question ? getOfficialAnswer(question.categoryKey) : ''),
        [question?.categoryKey]
    )

    if (!question) return null

    const handleToggleBookmark = (type: BookMarkType) => {
        const next = toggleBookmark(
            question.id,
            question.title,
            question.category,
            question.roundType,
            question.difficulty,
            question.positionKey,
            type
        )
        setBookmarks(getBookmarkTypesForQuestion(question.id))
        return next
    }

    const handleAddComment = () => {
        const text = newComment.trim()
        if (!text) return
        const name = nickname.trim() || '匿名用户'
        addDiscussion(question.id, name, '', text, false)
        setDiscussions(getDiscussionsForQuestion(question.id))
        setNewComment('')
    }

    const handleLike = (discussionId: string) => {
        likeDiscussion(discussionId)
        setDiscussions(getDiscussionsForQuestion(question.id))
    }

    const isFav = bookmarks.includes('favorite')
    const isMistake = bookmarks.includes('mistake')
    const isReview = bookmarks.includes('review')

    return createPortal(
        <div
            className="fixed inset-0 z-[100] flex items-center justify-center bg-[rgba(17,17,17,0.32)] p-4 sm:p-6"
            onClick={onClose}
        >
            <div
                className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-[28px] bg-[#FAF9F6] shadow-[0_24px_72px_rgba(17,17,17,0.24)] dark:border dark:border-[#2d3542] dark:bg-[#181c24]"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-start justify-between gap-4 border-b border-[#E5E5E5] px-6 py-5 dark:border-[#2d3542]">
                    <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                            <span className="rounded-full bg-[#EBE9E0] px-2.5 py-0.5 text-xs font-medium text-[#6B5E49] dark:bg-[#2d3542] dark:text-[#D6C7A6]">
                                {question.category}
                            </span>
                            <span
                                className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                                    question.difficulty === 'Easy'
                                        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300'
                                        : question.difficulty === 'Hard'
                                            ? 'bg-orange-50 text-orange-700 dark:bg-orange-950/30 dark:text-orange-300'
                                            : 'bg-[#F3F1EB] text-[#6B5E49] dark:bg-[#2d3542] dark:text-[#D6C7A6]'
                                }`}
                            >
                                {question.difficulty}
                            </span>
                        </div>
                        <h2 className="mt-3 text-xl font-semibold text-[#111111] dark:text-[#f4f7fb]">
                            {question.title}
                        </h2>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[#666666] transition hover:bg-[#F0ECE3] hover:text-[#111111] dark:text-[#bcc5d3]"
                    >
                        <X className="h-5 w-5" />
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-[#E5E5E5] px-6 dark:border-[#2d3542]">
                    <button
                        type="button"
                        onClick={() => setActiveTab('overview')}
                        className={`relative px-4 py-3 text-sm font-medium transition ${
                            activeTab === 'overview'
                                ? 'text-[#111111] dark:text-[#f4f7fb]'
                                : 'text-[#999999] hover:text-[#666666] dark:text-[#8e98aa]'
                        }`}
                    >
                        题目概览
                        {activeTab === 'overview' && (
                            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#111111] dark:bg-[#f4f7fb]" />
                        )}
                    </button>
                    <button
                        type="button"
                        onClick={() => setActiveTab('discussion')}
                        className={`relative px-4 py-3 text-sm font-medium transition ${
                            activeTab === 'discussion'
                                ? 'text-[#111111] dark:text-[#f4f7fb]'
                                : 'text-[#999999] hover:text-[#666666] dark:text-[#8e98aa]'
                        }`}
                    >
                        讨论区 ({discussions.length})
                        {activeTab === 'discussion' && (
                            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#111111] dark:bg-[#f4f7fb]" />
                        )}
                    </button>
                </div>

                {/* Content */}
                <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-5">
                    {activeTab === 'overview' ? (
                        <div className="space-y-6">
                            {/* Meta info */}
                            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                                <div className="rounded-2xl border border-[#E5E5E5] bg-white p-3 dark:border-[#2d3542] dark:bg-[#101217]">
                                    <div className="text-xs text-[#999999] dark:text-[#8e98aa]">岗位</div>
                                    <div className="mt-1 text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">{question.positionLabel}</div>
                                </div>
                                <div className="rounded-2xl border border-[#E5E5E5] bg-white p-3 dark:border-[#2d3542] dark:bg-[#101217]">
                                    <div className="text-xs text-[#999999] dark:text-[#8e98aa]">轮次</div>
                                    <div className="mt-1 text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">
                                        {question.roundType === 'technical' ? '技术基础面' : question.roundType === 'project' ? '项目深度面' : question.roundType === 'system_design' ? '系统设计面' : 'HR 综合面'}
                                    </div>
                                </div>
                                <div className="rounded-2xl border border-[#E5E5E5] bg-white p-3 dark:border-[#2d3542] dark:bg-[#101217]">
                                    <div className="text-xs text-[#999999] dark:text-[#8e98aa]">难度</div>
                                    <div className="mt-1 text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">{question.difficulty}</div>
                                </div>
                                <div className="rounded-2xl border border-[#E5E5E5] bg-white p-3 dark:border-[#2d3542] dark:bg-[#101217]">
                                    <div className="text-xs text-[#999999] dark:text-[#8e98aa]">频率</div>
                                    <div className="mt-1 text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">{question.frequency}</div>
                                </div>
                            </div>

                            {/* Bookmark actions */}
                            <div className="flex flex-wrap gap-2">
                                <button
                                    type="button"
                                    onClick={() => handleToggleBookmark('favorite')}
                                    className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition ${
                                        isFav
                                            ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800/60 dark:bg-amber-950/30 dark:text-amber-300'
                                            : 'border-[#E5E5E5] bg-white text-[#666666] hover:bg-[#F3F1EB] hover:text-[#111111] dark:border-[#2d3542] dark:bg-[#101217] dark:text-[#bcc5d3]'
                                    }`}
                                >
                                    {isFav ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
                                    {isFav ? '已收藏' : '收藏题目'}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => handleToggleBookmark('mistake')}
                                    className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition ${
                                        isMistake
                                            ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-800/60 dark:bg-red-950/30 dark:text-red-300'
                                            : 'border-[#E5E5E5] bg-white text-[#666666] hover:bg-[#F3F1EB] hover:text-[#111111] dark:border-[#2d3542] dark:bg-[#101217] dark:text-[#bcc5d3]'
                                    }`}
                                >
                                    {isMistake ? <Star className="h-4 w-4 fill-current" /> : <Star className="h-4 w-4" />}
                                    {isMistake ? '已标记错题' : '标记错题'}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => handleToggleBookmark('review')}
                                    className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition ${
                                        isReview
                                            ? 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-800/60 dark:bg-sky-950/30 dark:text-sky-300'
                                            : 'border-[#E5E5E5] bg-white text-[#666666] hover:bg-[#F3F1EB] hover:text-[#111111] dark:border-[#2d3542] dark:bg-[#101217] dark:text-[#bcc5d3]'
                                    }`}
                                >
                                    {isReview ? <Heart className="h-4 w-4 fill-current" /> : <Heart className="h-4 w-4" />}
                                    {isReview ? '已加入复习' : '重点复习'}
                                </button>
                            </div>

                            {/* Official answer */}
                            <div className="rounded-2xl border border-[#E5E5E5] bg-white p-5 dark:border-[#2d3542] dark:bg-[#101217]">
                                <div className="flex items-center gap-2">
                                    <ShieldCheck className="h-4 w-4 text-[#8B6F3D] dark:text-[#D6C7A6]" />
                                    <h3 className="text-sm font-semibold text-[#111111] dark:text-[#f4f7fb]">官方参考答案</h3>
                                </div>
                                <p className="mt-3 text-sm leading-7 text-[#666666] dark:text-[#bcc5d3]">{officialAnswer}</p>
                            </div>

                            {/* Practice button */}
                            <Button
                                size="lg"
                                className="w-full gap-2"
                                onClick={() => onPractice(question)}
                            >
                                <Play size={14} fill="currentColor" /> 开始练习这道题
                            </Button>
                        </div>
                    ) : (
                        <div className="space-y-5">
                            {/* Add comment */}
                            <div className="rounded-2xl border border-[#E5E5E5] bg-white p-4 dark:border-[#2d3542] dark:bg-[#101217]">
                                <div className="text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">参与讨论</div>
                                <textarea
                                    value={newComment}
                                    onChange={(e) => setNewComment(e.target.value)}
                                    placeholder="分享你的思路、经验或疑问..."
                                    className="mt-3 w-full rounded-xl border border-[#DED7CB] bg-[#FAF9F6] px-4 py-3 text-sm text-[#111111] outline-none transition focus:border-[#9A8767] dark:border-[#3A4658] dark:bg-[#0C1017] dark:text-[#f4f7fb]"
                                    rows={3}
                                />
                                <div className="mt-3 flex items-center justify-between">
                                    <input
                                        value={nickname}
                                        onChange={(e) => setNickname(e.target.value)}
                                        placeholder="你的昵称"
                                        className="h-9 rounded-lg border border-[#E5E5E5] bg-[#FAF9F6] px-3 text-sm text-[#111111] outline-none focus:border-[#9A8767] dark:border-[#3A4658] dark:bg-[#0C1017] dark:text-[#f4f7fb]"
                                    />
                                    <Button
                                        size="sm"
                                        disabled={!newComment.trim()}
                                        onClick={handleAddComment}
                                        className="gap-1.5"
                                    >
                                        <Send className="h-3.5 w-3.5" />
                                        发送
                                    </Button>
                                </div>
                            </div>

                            {/* Discussion list */}
                            {discussions.length === 0 ? (
                                <div className="py-10 text-center text-sm text-[#999999] dark:text-[#8e98aa]">
                                    <MessageCircle className="mx-auto mb-2 h-8 w-8 opacity-40" />
                                    暂无讨论，来做第一个发言的人吧
                                </div>
                            ) : (
                                discussions.map((item) => (
                                    <div
                                        key={item.id}
                                        className="rounded-2xl border border-[#E5E5E5] bg-white p-4 dark:border-[#2d3542] dark:bg-[#101217]"
                                    >
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#EBE9E0] text-xs font-semibold text-[#6B5E49] dark:bg-[#2d3542] dark:text-[#D6C7A6]">
                                                    {item.author.slice(0, 2)}
                                                </div>
                                                <div>
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">{item.author}</span>
                                                        {item.isOfficial && (
                                                            <span className="rounded-full bg-[#F3F1EB] px-2 py-0.5 text-[10px] font-medium text-[#8B6F3D] dark:bg-[#2d3542] dark:text-[#D6C7A6]">
                                                                官方
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div className="text-xs text-[#999999] dark:text-[#8e98aa]">{formatTime(item.createdAt)}</div>
                                                </div>
                                            </div>
                                            <button
                                                type="button"
                                                onClick={() => handleLike(item.id)}
                                                className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-[#999999] transition hover:bg-[#F3F1EB] hover:text-[#111111] dark:text-[#8e98aa] dark:hover:bg-[#2d3542] dark:hover:text-[#f4f7fb]"
                                            >
                                                <ThumbsUp className="h-3.5 w-3.5" />
                                                {item.likes}
                                            </button>
                                        </div>
                                        <p className="mt-3 text-sm leading-6 text-[#444444] dark:text-[#bcc5d3]">{item.content}</p>
                                    </div>
                                ))
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>,
        document.body
    )
}

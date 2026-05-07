'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
    ArrowLeft,
    Bookmark,
    BookOpen,
    Heart,
    MessageSquare,
    Play,
    Star,
    Trash2,
} from 'lucide-react'
import { motion } from 'motion/react'
import {
    getBookmarks,
    getBookmarksByType,
    removeBookmark,
    type BookMarkType,
    type QuestionBookItem,
} from '@/lib/question-book'

const TABS: { key: BookMarkType | 'all'; label: string; icon: typeof Bookmark }[] = [
    { key: 'all', label: '全部', icon: Bookmark },
    { key: 'favorite', label: '我的收藏', icon: Bookmark },
    { key: 'mistake', label: '错题本', icon: Star },
    { key: 'review', label: '重点复习', icon: Heart },
]

function toDifficultyBadgeVariant(difficulty: string): 'success' | 'neutral' | 'warning' {
    const d = difficulty.toLowerCase()
    if (d === 'easy' || d === '简单') return 'success'
    if (d === 'hard' || d === '困难') return 'warning'
    return 'neutral'
}

function difficultyLabel(difficulty: string): string {
    const d = difficulty.toLowerCase()
    if (d === 'easy' || d === '简单') return '简单'
    if (d === 'hard' || d === '困难') return '困难'
    return '中等'
}

function roundLabel(roundType: string): string {
    if (roundType === 'technical') return '技术基础面'
    if (roundType === 'project') return '项目深度面'
    if (roundType === 'system_design') return '系统设计面'
    if (roundType === 'hr') return 'HR 综合面'
    return roundType
}

function positionLabel(key: string): string {
    const map: Record<string, string> = {
        common: '通用高频',
        java_backend: 'Java 后端工程师',
        frontend: '前端工程师',
        test_engineer: '软件测试工程师',
        agent_developer: 'Agent开发工程师',
        product_manager: '产品经理',
        algorithm: '算法工程师',
    }
    return map[key] || key
}

export default function BookmarksPage() {
    const router = useRouter()
    const [activeTab, setActiveTab] = useState<BookMarkType | 'all'>('all')
    const [items, setItems] = useState<QuestionBookItem[]>([])
    const [version, setVersion] = useState(0)

    useEffect(() => {
        setItems(getBookmarks())
    }, [version])

    const filteredItems = useMemo(() => {
        if (activeTab === 'all') return items
        return getBookmarksByType(activeTab)
    }, [activeTab, items])

    const handleRemove = (questionId: string, type: BookMarkType) => {
        removeBookmark(questionId, type)
        setVersion((v) => v + 1)
    }

    const handlePractice = (item: QuestionBookItem) => {
        const config = {
            round: item.roundType,
            position: item.positionKey,
            difficulty: item.difficulty,
            trainingTaskId: '',
            trainingMode: '',
            selectedQuestion: {
                id: item.questionId,
                question: item.questionTitle,
                category: item.category,
                round_type: item.roundType,
                position: item.positionKey,
                difficulty: item.difficulty,
            },
        }
        sessionStorage.setItem('interview_config', JSON.stringify(config))
        router.push('/interview')
    }

    const stats = useMemo(() => {
        return {
            total: items.length,
            favorite: items.filter((i) => i.type === 'favorite').length,
            mistake: items.filter((i) => i.type === 'mistake').length,
            review: items.filter((i) => i.type === 'review').length,
        }
    }, [items])

    return (
        <div className="flex-1 min-h-0 overflow-y-auto p-8 lg:p-12">
            <div className="max-w-5xl mx-auto space-y-8">
                <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                        <Link
                            href="/dashboard/questions"
                            className="inline-flex items-center gap-1 text-sm text-[var(--ink-muted)] hover:text-[var(--ink)] transition"
                        >
                            <ArrowLeft size={14} />
                            返回题库
                        </Link>
                        <h1 className="mt-3 text-3xl font-serif text-[var(--ink)] tracking-tight">我的题本</h1>
                        <p className="text-[var(--ink-muted)] mt-2">管理收藏、错题和重点复习题目。</p>
                    </motion.div>
                </header>

                {/* Stats */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.1 }}
                    className="grid grid-cols-2 md:grid-cols-4 gap-4"
                >
                    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
                        <div className="text-xs text-[var(--ink-lighter)]">全部</div>
                        <div className="mt-1 text-2xl font-semibold text-[var(--ink)]">{stats.total}</div>
                    </div>
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-800/40 dark:bg-amber-950/20">
                        <div className="text-xs text-amber-600 dark:text-amber-300">收藏</div>
                        <div className="mt-1 text-2xl font-semibold text-amber-700 dark:text-amber-300">{stats.favorite}</div>
                    </div>
                    <div className="rounded-2xl border border-red-200 bg-red-50 p-4 dark:border-red-800/40 dark:bg-red-950/20">
                        <div className="text-xs text-red-600 dark:text-red-300">错题</div>
                        <div className="mt-1 text-2xl font-semibold text-red-700 dark:text-red-300">{stats.mistake}</div>
                    </div>
                    <div className="rounded-2xl border border-sky-200 bg-sky-50 p-4 dark:border-sky-800/40 dark:bg-sky-950/20">
                        <div className="text-xs text-sky-600 dark:text-sky-300">复习</div>
                        <div className="mt-1 text-2xl font-semibold text-sky-700 dark:text-sky-300">{stats.review}</div>
                    </div>
                </motion.div>

                {/* Tabs */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.2 }}
                    className="flex flex-wrap gap-2"
                >
                    {TABS.map((tab) => {
                        const Icon = tab.icon
                        return (
                            <button
                                key={tab.key}
                                onClick={() => setActiveTab(tab.key)}
                                className={`inline-flex items-center gap-2 px-4 py-2 text-sm rounded-full border transition-all duration-200 ${
                                    activeTab === tab.key
                                        ? 'bg-[#111111] text-white border-[#111111]'
                                        : 'bg-[var(--surface)] text-[var(--ink-muted)] border-[var(--border)] hover:bg-[var(--accent)] hover:text-[var(--ink)]'
                                }`}
                            >
                                <Icon size={14} />
                                {tab.label}
                            </button>
                        )
                    })}
                </motion.div>

                {/* List */}
                <div className="space-y-4">
                    {filteredItems.length === 0 ? (
                        <div className="py-16 text-center">
                            <BookOpen className="mx-auto mb-3 h-10 w-10 text-[var(--ink-lighter)] opacity-40" />
                            <p className="text-[var(--ink-muted)]">
                                {activeTab === 'all'
                                    ? '还没有收藏任何题目，去题库看看吧。'
                                    : `暂无${TABS.find((t) => t.key === activeTab)?.label}记录。`}
                            </p>
                            <Link
                                href="/dashboard/questions"
                                className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-[var(--ink)] hover:underline"
                            >
                                前往题库 <ArrowLeft size={14} className="rotate-180" />
                            </Link>
                        </div>
                    ) : (
                        filteredItems.map((item, index) => (
                            <motion.div
                                key={`${item.questionId}_${item.type}`}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: index * 0.03 }}
                            >
                                <Card className="p-5 flex flex-col sm:flex-row sm:items-center gap-4 hover:border-[var(--ink)] transition-all">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <span className="text-xs font-medium text-[var(--ink-lighter)] uppercase tracking-wider">
                                                {item.category}
                                            </span>
                                            <Badge variant={toDifficultyBadgeVariant(item.difficulty)}>
                                                {difficultyLabel(item.difficulty)}
                                            </Badge>
                                            <span
                                                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                                                    item.type === 'favorite'
                                                        ? 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300'
                                                        : item.type === 'mistake'
                                                            ? 'bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300'
                                                            : 'bg-sky-50 text-sky-700 dark:bg-sky-950/30 dark:text-sky-300'
                                                }`}
                                            >
                                                {item.type === 'favorite' && <Bookmark size={10} />}
                                                {item.type === 'mistake' && <Star size={10} />}
                                                {item.type === 'review' && <Heart size={10} />}
                                                {item.type === 'favorite' ? '收藏' : item.type === 'mistake' ? '错题' : '复习'}
                                            </span>
                                        </div>
                                        <h3 className="mt-2 text-base font-medium text-[var(--ink)] leading-snug truncate">
                                            {item.questionTitle}
                                        </h3>
                                        <div className="mt-2 flex items-center gap-3 text-xs text-[var(--ink-lighter)]">
                                            <span>{positionLabel(item.positionKey)}</span>
                                            <span>·</span>
                                            <span>{roundLabel(item.roundType)}</span>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        <Button
                                            size="sm"
                                            variant="secondary"
                                            className="gap-1.5"
                                            onClick={() => handlePractice(item)}
                                        >
                                            <Play size={12} fill="currentColor" />
                                            练习
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/20"
                                            onClick={() => handleRemove(item.questionId, item.type)}
                                        >
                                            <Trash2 size={14} />
                                        </Button>
                                    </div>
                                </Card>
                            </motion.div>
                        ))
                    )}
                </div>
            </div>
        </div>
    )
}

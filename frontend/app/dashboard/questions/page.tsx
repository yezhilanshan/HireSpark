'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Play, Search, BookOpen, Bookmark, Star, Heart, Library } from 'lucide-react'
import { motion, AnimatePresence } from 'motion/react'
import { getBackendBaseUrl } from '@/lib/backend'
import { readPageCache, writePageCache } from '@/lib/page-cache'
import Link from 'next/link'
import QuestionDetailModal from '@/components/QuestionDetailModal'
import { isBookmarked, type BookMarkType } from '@/lib/question-book'

const BACKEND_API_BASE = getBackendBaseUrl()
const QUESTION_PAGE_SIZE = 10
const QUESTION_CACHE_KEY = 'zhiyuexingchen.page.questions.v1'
const QUESTION_CACHE_TTL_MS = 1000 * 60 * 20

type QuestionItem = {
    id: string
    question: string
    category?: string
    round_type?: string
    position?: string
    difficulty?: string
    frequency?: string
    source?: string
}

type QuestionBankApiResult = {
    success: boolean
    question_bank?: QuestionItem[]
    categories?: string[]
    message?: string
    error?: string
}

type QuestionBankCacheData = {
    questions: QuestionItem[]
}

const POSITION_TAGS = [
    { key: 'common', label: '通用高频' },
    { key: 'java_backend', label: 'Java 后端工程师' },
    { key: 'frontend', label: '前端工程师' },
    { key: 'test_engineer', label: '软件测试工程师' },
    { key: 'agent_developer', label: 'Agent开发工程师' },
    { key: 'product_manager', label: '产品经理' },
    { key: 'algorithm', label: '算法工程师' },
] as const

function normalizePositionKey(raw?: string): string {
    const text = String(raw || '')
        .replace(/[\u200b-\u200d\ufeff]/g, '')
        .replace(/\s+/g, ' ')
        .trim()
        .toLowerCase()

    if (!text) return ''
    if (
        text.includes('java_backend')
        || (text.includes('java') && (text.includes('backend') || text.includes('后端')))
        || text === 'backend'
        || text === 'backend_engineer'
        || text.includes('后端')
        || (text.includes('backend') && !text.includes('frontend'))
    ) return 'java_backend'
    if (text.includes('frontend') || text.includes('前端') || text.includes('qianduan')) return 'frontend'
    if (text.includes('test_engineer') || text.includes('software_test') || text.includes('qa') || text.includes('测试') || text.includes('软件测试') || text.includes('fullstack') || text.includes('全栈')) return 'test_engineer'
    if (
        text.includes('agent_developer')
        || text.includes('agent开发')
        || text.includes('智能体')
        || text.includes('agent')
        || text.includes('data_engineer')
        || text.includes('数据工程')
    ) return 'agent_developer'
    if (text.includes('product_manager') || text.includes('产品') || text.includes(' pm ') || text.endsWith('pm')) return 'product_manager'
    if (text.includes('algorithm') || text.includes('算法')) return 'algorithm'
    return ''
}

function positionLabelFromKey(key: string): string {
    const matched = POSITION_TAGS.find((item) => item.key === key)
    return matched?.label || '未分类岗位'
}

function isCommonQuestionCategory(rawCategory?: string): boolean {
    const key = normalizeCategoryKey(rawCategory)
    if (!key) return false
    return (
        key.includes('面试综合')
        || key.includes('经验问答')
        || key.includes('行为面试')
        || key.includes('通用')
        || key.includes('面经整理')
    )
}

function normalizeCategoryLabel(raw?: string): string {
    const text = String(raw || '')
        .replace(/\u3000/g, ' ')
        .replace(/[\u200b-\u200d\ufeff]/g, '')
        .replace(/\s+/g, ' ')
        .trim()
    return text
}

function normalizeCategoryKey(raw?: string): string {
    return normalizeCategoryLabel(raw).toLowerCase()
}

function normalizeDifficulty(raw?: string): 'Easy' | 'Medium' | 'Hard' {
    const value = (raw || '').trim().toLowerCase()
    if (value === 'easy' || value === 'low' || value === '初级' || value === '简单') return 'Easy'
    if (value === 'hard' || value === 'high' || value === '高级' || value === '困难') return 'Hard'
    return 'Medium'
}

function normalizeDifficultyKey(raw?: string): 'easy' | 'medium' | 'hard' {
    const value = (raw || '').trim().toLowerCase()
    if (value === 'easy' || value === 'low' || value === '初级' || value === '简单') return 'easy'
    if (value === 'hard' || value === 'high' || value === '高级' || value === '困难') return 'hard'
    return 'medium'
}

function normalizeRoundType(raw?: string): 'technical' | 'project' | 'system_design' | 'hr' {
    const value = String(raw || '').trim().toLowerCase()
    if (value === 'project') return 'project'
    if (value === 'system_design' || value === 'system design' || value === 'system-design') return 'system_design'
    if (value === 'hr') return 'hr'
    return 'technical'
}

function toDifficultyBadgeVariant(difficulty: 'Easy' | 'Medium' | 'Hard'): 'success' | 'neutral' | 'warning' {
    if (difficulty === 'Easy') return 'success'
    if (difficulty === 'Hard') return 'warning'
    return 'neutral'
}

function normalizeSearchableText(raw?: string): string {
    return String(raw || '')
        .toLowerCase()
        .replace(/[\u3000\s]+/g, '')
        .replace(/[，。！？；：“”‘’、,.!?;:'"()[\]{}<>《》【】]/g, '')
        .trim()
}

export default function QuestionsPage() {
    const initialCache = typeof window === 'undefined'
        ? null
        : readPageCache<QuestionBankCacheData>(QUESTION_CACHE_KEY, QUESTION_CACHE_TTL_MS)
    const hasCachedQuestions = Boolean(initialCache?.questions?.length)

    const router = useRouter()
    const searchParams = useSearchParams()
    const [activePosition, setActivePosition] = useState<string>('common')
    const [forcedRoundType, setForcedRoundType] = useState<string>('')
    const [forcedDifficulty, setForcedDifficulty] = useState<string>('')
    const [trainingTaskId, setTrainingTaskId] = useState<string>('')
    const [trainingFocusLabel, setTrainingFocusLabel] = useState<string>('')
    const [searchQuery, setSearchQuery] = useState('')
    const [loading, setLoading] = useState(!initialCache)
    const [error, setError] = useState('')
    const [questions, setQuestions] = useState<QuestionItem[]>(initialCache?.questions || [])
    const [visibleCount, setVisibleCount] = useState<number>(QUESTION_PAGE_SIZE)
    type NormalizedQuestion = {
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

    const [selectedQuestion, setSelectedQuestion] = useState<NormalizedQuestion | null>(null)
    const [bookmarkVersion, setBookmarkVersion] = useState(0)

    const loadQuestionBank = useCallback(async (options?: { silent?: boolean; hasCached?: boolean }) => {
        const silent = Boolean(options?.silent)
        const hasCached = Boolean(options?.hasCached)

        if (!silent || !hasCached) {
            setLoading(true)
        }
        setError('')

        try {
            const endpoint = `${BACKEND_API_BASE}/api/question-bank?limit=1000`
            const res = await fetch(endpoint, { cache: 'no-store' })
            const data: QuestionBankApiResult = await res.json()

            if (!res.ok || !data.success) {
                throw new Error(data.error || data.message || '题库加载失败')
            }

            const bank = Array.isArray(data.question_bank) ? data.question_bank : []
            setQuestions(bank)
            writePageCache<QuestionBankCacheData>(QUESTION_CACHE_KEY, { questions: bank })
        } catch (err) {
            if (!hasCached) {
                setQuestions([])
                setError(err instanceof Error ? err.message : '题库加载失败')
            } else {
                setError('题库更新失败，已展示缓存数据。')
            }
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        void loadQuestionBank({ silent: hasCachedQuestions, hasCached: hasCachedQuestions })
    }, [loadQuestionBank])

    useEffect(() => {
        const positionParam = normalizePositionKey(searchParams.get('position') || '')
        if (positionParam) {
            setActivePosition(positionParam)
        }
        const roundTypeParam = String(searchParams.get('round_type') || '').trim()
        const difficultyParam = String(searchParams.get('difficulty') || '').trim()
        setForcedRoundType(roundTypeParam ? normalizeRoundType(roundTypeParam) : '')
        setForcedDifficulty(difficultyParam ? normalizeDifficultyKey(difficultyParam) : '')
        setTrainingTaskId(String(searchParams.get('training_task_id') || '').trim())
        setTrainingFocusLabel(String(searchParams.get('focus_label') || '').trim())
    }, [searchParams])

    const normalizedQuestions = useMemo(() => {
        return questions.map((item, index) => {
            const normalizedDifficulty = normalizeDifficulty(item.difficulty)
            const categoryLabel = normalizeCategoryLabel(item.category || item.round_type || '未分类') || '未分类'
            const rawPositionKey = normalizePositionKey(item.position)
            const effectivePositionKey = isCommonQuestionCategory(categoryLabel)
                ? 'common'
                : (rawPositionKey || 'common')
            const rawId = String(item.id || `${index + 1}`)
            const normalizedRound = normalizeRoundType(item.round_type)
            const normalizedDifficultyKey = normalizeDifficultyKey(item.difficulty)
            const sourceTag = String(item.source || '').trim().toLowerCase() || 'local'
            return {
                id: rawId,
                uiKey: [
                    rawId,
                    effectivePositionKey,
                    normalizedRound,
                    normalizedDifficultyKey,
                    normalizeCategoryKey(categoryLabel) || 'uncategorized',
                    sourceTag,
                    String(index),
                ].join('__'),
                title: (item.question || '').trim(),
                category: categoryLabel,
                categoryKey: normalizeCategoryKey(categoryLabel),
                positionKey: effectivePositionKey,
                positionLabel: positionLabelFromKey(effectivePositionKey),
                difficulty: normalizedDifficulty,
                difficultyKey: normalizedDifficultyKey,
                roundType: normalizedRound,
                sourcePositionKey: rawPositionKey,
                frequency: (item.frequency || 'N/A').trim(),
            }
        }).filter((item) => item.title)
    }, [questions])

    const normalizedSearchQuery = useMemo(() => normalizeSearchableText(searchQuery), [searchQuery])

    const filteredQuestions = useMemo(() => {
        return normalizedQuestions.filter((q) => {
            const matchesPosition = q.positionKey === activePosition
            if (!matchesPosition) return false
            const matchesRoundType = !forcedRoundType || q.roundType === forcedRoundType
            if (!matchesRoundType) return false
            const matchesDifficulty = !forcedDifficulty || q.difficultyKey === forcedDifficulty
            if (!matchesDifficulty) return false
            if (!normalizedSearchQuery) return true

            const searchCorpus = normalizeSearchableText(
                [
                    q.title,
                    q.category,
                    q.id,
                    q.positionLabel,
                    q.positionKey,
                    q.roundType,
                    q.frequency,
                ].join(' ')
            )

            return searchCorpus.includes(normalizedSearchQuery)
        })
    }, [activePosition, forcedDifficulty, forcedRoundType, normalizedQuestions, normalizedSearchQuery])

    useEffect(() => {
        setVisibleCount(QUESTION_PAGE_SIZE)
    }, [activePosition, normalizedSearchQuery])

    const visibleQuestions = useMemo(
        () => filteredQuestions.slice(0, visibleCount),
        [filteredQuestions, visibleCount]
    )

    const hasMoreQuestions = filteredQuestions.length > visibleQuestions.length
    const remainingQuestions = Math.max(filteredQuestions.length - visibleQuestions.length, 0)

    const handlePracticeQuestion = useCallback((question: (typeof filteredQuestions)[number]) => {
        const resolvedPosition = question.sourcePositionKey || (activePosition !== 'common' ? activePosition : 'java_backend')
        const config = {
            round: question.roundType,
            position: resolvedPosition,
            difficulty: question.difficultyKey,
            trainingTaskId,
            trainingMode: trainingTaskId ? 'plan_training' : '',
            selectedQuestion: {
                id: question.id,
                question: question.title,
                category: question.category,
                round_type: question.roundType,
                position: resolvedPosition,
                difficulty: question.difficultyKey,
            },
        }
        sessionStorage.setItem('interview_config', JSON.stringify(config))
        router.push('/interview')
    }, [activePosition, router, trainingTaskId])

    return (
        <div className="flex-1 min-h-0 overflow-y-auto p-8 lg:p-12">
            <div className="max-w-5xl mx-auto space-y-8">
                <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                        <h1 className="text-3xl font-serif text-[var(--ink)] tracking-tight">题库</h1>
                        <p className="text-[var(--ink-muted)] mt-2">按能力维度练习高频题，构建稳定回答框架。</p>
                    </motion.div>

                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="flex items-center gap-3">
                        <Link
                            href="/dashboard/questions/bookmarks"
                            className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-sm text-[var(--ink-muted)] transition hover:bg-[var(--accent)] hover:text-[var(--ink)]"
                        >
                            <Library size={16} />
                            我的题本
                        </Link>
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ink-lighter)]" size={16} />
                            <input
                                type="text"
                                placeholder="搜索题目/分类/岗位关键词..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="h-10 pl-9 pr-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm focus:outline-none focus:border-[var(--ink)] focus:ring-1 focus:ring-[var(--ink)] transition-all w-full md:w-64"
                            />
                        </div>
                    </motion.div>
                </header>

                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }} className="flex flex-wrap gap-2">
                    {POSITION_TAGS.map((position) => (
                        <button
                            key={position.key}
                            onClick={() => setActivePosition(position.key)}
                            className={`px-4 py-1.5 text-sm rounded-full border transition-all duration-200 ${activePosition === position.key
                                ? 'bg-[#111111] text-white border-[#111111]'
                                : 'bg-[var(--surface)] text-[var(--ink-muted)] border-[var(--border)] hover:bg-[var(--accent)] hover:text-[var(--ink)]'
                                }`}
                        >
                            {position.label}
                        </button>
                    ))}
                </motion.div>
                {normalizedSearchQuery ? (
                    <p className="text-xs text-[var(--ink-lighter)]">已启用全局搜索：输入关键词时会跨岗位检索题目。</p>
                ) : null}
                {trainingTaskId ? (
                    <div className="rounded-xl border border-[#E7DDCC] bg-[#FDF8EF] px-4 py-3 text-sm text-[#6F5830]">
                        <p>当前正在执行训练任务：{trainingTaskId}</p>
                        <p className="mt-1 text-xs text-[#8B744D]">
                            {trainingFocusLabel ? `训练焦点：${trainingFocusLabel}` : '已按任务自动筛选轮次与难度，建议直接进行答题训练。'}
                        </p>
                    </div>
                ) : null}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {loading && (
                        <div className="col-span-full py-12 text-center text-[var(--ink-muted)]">
                            正在从后端加载题库...
                        </div>
                    )}
                    {!loading && error && (
                        <div className="col-span-full rounded-xl border border-red-200 bg-red-50 px-4 py-5 text-sm text-red-700">
                            <p>{error}</p>
                            <Button
                                size="sm"
                                variant="secondary"
                                className="mt-3"
                                onClick={() => void loadQuestionBank({ hasCached: questions.length > 0 })}
                            >
                                重新加载
                            </Button>
                        </div>
                    )}
                    {visibleQuestions.map((q) => {
                        const bookmarkTypes = isBookmarked(q.id) ? [1] : []
                        return (
                            <motion.div
                                key={q.uiKey}
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ duration: 0.2 }}
                            >
                                <Card
                                    className="p-6 h-full flex flex-col justify-between hover:border-[var(--ink)] hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)] transition-all duration-300 group cursor-pointer"
                                    onClick={() => setSelectedQuestion(q)}
                                >
                                    <div className="space-y-4">
                                        <div className="flex items-center justify-between">
                                            <span className="text-xs font-medium text-[var(--ink-lighter)] uppercase tracking-wider">{q.category}</span>
                                            <div className="flex items-center gap-2">
                                                {bookmarkTypes.length > 0 && (
                                                    <Bookmark className="h-3.5 w-3.5 text-amber-500" fill="currentColor" />
                                                )}
                                                <Badge variant={toDifficultyBadgeVariant(q.difficulty)}>
                                                    {q.difficulty}
                                                </Badge>
                                            </div>
                                        </div>
                                        <h3 className="text-lg font-medium text-[var(--ink)] leading-snug">"{q.title}"</h3>
                                    </div>

                                    <div className="mt-8 flex items-center justify-between pt-4 border-t border-[var(--border)]">
                                        <div className="text-sm text-[var(--ink-muted)] flex items-center gap-1.5">
                                            <BookOpen size={14} />
                                            Frequency: {q.frequency}
                                        </div>
                                        <Button
                                            size="sm"
                                            variant="secondary"
                                            className="gap-2 opacity-0 group-hover:opacity-100 transition-opacity"
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                handlePracticeQuestion(q)
                                            }}
                                        >
                                            <Play size={12} fill="currentColor" /> 直接作答
                                        </Button>
                                    </div>
                                </Card>
                            </motion.div>
                        )
                    })}
                    {!loading && !error && hasMoreQuestions && (
                        <div className="col-span-full flex justify-center pt-2">
                            <Button
                                variant="secondary"
                                className="px-6"
                                onClick={() => setVisibleCount((prev) => prev + QUESTION_PAGE_SIZE)}
                            >
                                查看更多（剩余 {remainingQuestions} 题）
                            </Button>
                        </div>
                    )}
                    {!loading && !error && filteredQuestions.length === 0 && (
                        <div className="col-span-full py-12 text-center text-[var(--ink-muted)]">
                            {normalizedQuestions.length === 0 ? '题库暂无数据，请先在后端数据库中写入题目。' : '当前岗位下暂无匹配题目，请切换岗位或搜索关键词。'}
                        </div>
                    )}
                </div>
            </div>

            <QuestionDetailModal
                question={selectedQuestion}
                onClose={() => {
                    setSelectedQuestion(null)
                    setBookmarkVersion((v) => v + 1)
                }}
                onPractice={(q) => {
                    setSelectedQuestion(null)
                    handlePracticeQuestion(q)
                }}
            />
        </div>
    )
}

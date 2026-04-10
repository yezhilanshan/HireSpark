'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Play, Search, BookOpen } from 'lucide-react'
import Link from 'next/link'
import { motion, AnimatePresence } from 'motion/react'
import { getBackendBaseUrl } from '@/lib/backend'

const BACKEND_API_BASE = getBackendBaseUrl()

type QuestionItem = {
    id: string
    question: string
    category?: string
    round_type?: string
    position?: string
    difficulty?: string
    frequency?: string
}

type QuestionBankApiResult = {
    success: boolean
    question_bank?: QuestionItem[]
    categories?: string[]
    message?: string
    error?: string
}

function normalizeDifficulty(raw?: string): 'Easy' | 'Medium' | 'Hard' {
    const value = (raw || '').trim().toLowerCase()
    if (value === 'easy' || value === 'low' || value === '初级' || value === '简单') return 'Easy'
    if (value === 'hard' || value === 'high' || value === '高级' || value === '困难') return 'Hard'
    return 'Medium'
}

function toDifficultyBadgeVariant(difficulty: 'Easy' | 'Medium' | 'Hard'): 'success' | 'neutral' | 'warning' {
    if (difficulty === 'Easy') return 'success'
    if (difficulty === 'Hard') return 'warning'
    return 'neutral'
}

export default function QuestionsPage() {
    const [activeCategory, setActiveCategory] = useState('All')
    const [searchQuery, setSearchQuery] = useState('')
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [questions, setQuestions] = useState<QuestionItem[]>([])
    const [apiCategories, setApiCategories] = useState<string[]>([])

    const loadQuestionBank = useCallback(async () => {
        setLoading(true)
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
            setApiCategories(Array.isArray(data.categories) ? data.categories.filter(Boolean) : [])
        } catch (err) {
            setQuestions([])
            setApiCategories([])
            setError(err instanceof Error ? err.message : '题库加载失败')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        loadQuestionBank()
    }, [loadQuestionBank])

    const categories = useMemo(() => {
        const fromQuestions = new Set(
            questions
                .map((item) => (item.category || '').trim())
                .filter(Boolean)
        )
        for (const category of apiCategories) {
            fromQuestions.add(category.trim())
        }
        return ['All', ...Array.from(fromQuestions)]
    }, [questions, apiCategories])

    useEffect(() => {
        if (activeCategory === 'All') return
        if (categories.includes(activeCategory)) return
        setActiveCategory('All')
    }, [activeCategory, categories])

    const normalizedQuestions = useMemo(() => {
        return questions.map((item, index) => {
            const normalizedDifficulty = normalizeDifficulty(item.difficulty)
            return {
                id: String(item.id || `${index + 1}`),
                title: (item.question || '').trim(),
                category: (item.category || item.round_type || '未分类').trim(),
                difficulty: normalizedDifficulty,
                frequency: (item.frequency || 'N/A').trim(),
            }
        }).filter((item) => item.title)
    }, [questions])

    const filteredQuestions = normalizedQuestions.filter((q) => {
        const matchesCategory = activeCategory === 'All' || q.category === activeCategory
        const matchesSearch = q.title.toLowerCase().includes(searchQuery.toLowerCase())
        return matchesCategory && matchesSearch
    })

    return (
        <div className="flex-1 overflow-y-auto p-8 lg:p-12">
            <div className="max-w-5xl mx-auto space-y-8">
                <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                        <h1 className="text-3xl font-serif text-[#111111] tracking-tight">题库</h1>
                        <p className="text-[#666666] mt-2">按能力维度练习高频题，构建稳定回答框架。</p>
                    </motion.div>

                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="flex items-center gap-3">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[#999999]" size={16} />
                            <input
                                type="text"
                                placeholder="搜索题目..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="h-10 pl-9 pr-4 rounded-lg border border-[#E5E5E5] bg-white text-sm focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] transition-all w-full md:w-64"
                            />
                        </div>
                    </motion.div>
                </header>

                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }} className="flex flex-wrap gap-2">
                    {categories.map((category) => (
                        <button
                            key={category}
                            onClick={() => setActiveCategory(category)}
                            className={`px-4 py-1.5 text-sm rounded-full border transition-all duration-200 ${
                                activeCategory === category
                                    ? 'bg-[#111111] text-white border-[#111111]'
                                    : 'bg-white text-[#666666] border-[#E5E5E5] hover:bg-[#F5F5F5] hover:text-[#111111]'
                            }`}
                        >
                            {category}
                        </button>
                    ))}
                </motion.div>

                <motion.div layout className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <AnimatePresence mode="popLayout">
                        {loading && (
                            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="col-span-full py-12 text-center text-[#666666]">
                                正在从后端加载题库...
                            </motion.div>
                        )}
                        {!loading && error && (
                            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="col-span-full rounded-xl border border-red-200 bg-red-50 px-4 py-5 text-sm text-red-700">
                                <p>{error}</p>
                                <Button size="sm" variant="secondary" className="mt-3" onClick={loadQuestionBank}>
                                    重新加载
                                </Button>
                            </motion.div>
                        )}
                        {filteredQuestions.map((q) => (
                            <motion.div
                                key={q.id}
                                layout
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.95 }}
                                transition={{ duration: 0.2 }}
                            >
                                <Card className="p-6 h-full flex flex-col justify-between hover:border-[#111111] hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)] transition-all duration-300 group">
                                    <div className="space-y-4">
                                        <div className="flex items-center justify-between">
                                            <span className="text-xs font-medium text-[#999999] uppercase tracking-wider">{q.category}</span>
                                            <Badge variant={toDifficultyBadgeVariant(q.difficulty)}>
                                                {q.difficulty}
                                            </Badge>
                                        </div>
                                        <h3 className="text-lg font-medium text-[#111111] leading-snug">“{q.title}”</h3>
                                    </div>

                                    <div className="mt-8 flex items-center justify-between pt-4 border-t border-[#E5E5E5]">
                                        <div className="text-sm text-[#666666] flex items-center gap-1.5">
                                            <BookOpen size={14} />
                                            Frequency: {q.frequency}
                                        </div>
                                        <Link href="/interview/setup">
                                            <Button size="sm" variant="secondary" className="gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                                <Play size={12} fill="currentColor" /> Practice
                                            </Button>
                                        </Link>
                                    </div>
                                </Card>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                    {!loading && !error && filteredQuestions.length === 0 && (
                        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="col-span-full py-12 text-center text-[#666666]">
                            {normalizedQuestions.length === 0 ? '题库暂无数据，请先在后端数据库中写入题目。' : 'No questions found matching your criteria.'}
                        </motion.div>
                    )}
                </motion.div>
            </div>
        </div>
    )
}

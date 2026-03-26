'use client'

import { useRouter } from 'next/navigation'
import { Activity, Radar, Sparkles, FileText, ArrowRight } from 'lucide-react'

export default function Home() {
    const router = useRouter()

    const handleStartInterview = () => {
        router.push('/interview-setup')
    }

    const handleViewInsights = () => {
        router.push('/report')
    }

    return (
        <main className="relative min-h-screen overflow-hidden p-4 transition-colors sm:p-8">
            <div className="pointer-events-none absolute inset-0">
                <div className="absolute -left-20 top-10 h-56 w-56 rounded-full bg-cyan-400/20 blur-3xl" />
                <div className="absolute right-4 top-24 h-64 w-64 rounded-full bg-orange-300/20 blur-3xl" />
                <div className="absolute bottom-10 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-emerald-400/15 blur-3xl" />
            </div>

            <div className="relative mx-auto flex min-h-[calc(100vh-2rem)] w-full max-w-6xl flex-col justify-center">
                <section className="glass-panel animate-slide-up rounded-3xl p-6 shadow-2xl shadow-cyan-950/10 sm:p-10">
                    <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
                        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-700/20 bg-cyan-50/80 px-4 py-2 text-sm font-semibold text-cyan-800 dark:border-cyan-300/30 dark:bg-cyan-900/20 dark:text-cyan-200">
                            <Sparkles className="h-4 w-4" />
                            天枢智面 · AI 模拟面试平台
                        </div>
                        <div className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-xs font-bold uppercase tracking-widest text-white dark:bg-slate-100 dark:text-slate-900">
                            AI INTERVIEW COACH
                        </div>
                    </div>

                    <div className="grid gap-8 lg:grid-cols-[1.3fr_1fr]">
                        <div>
                            <h1 className="text-4xl font-black leading-tight text-slate-900 dark:text-slate-100 sm:text-6xl">
                                天枢智面
                                <span className="block bg-gradient-to-r from-cyan-600 to-orange-500 bg-clip-text text-transparent">让每一次面试都可量化成长</span>
                            </h1>
                            <p className="mt-5 max-w-2xl text-base leading-relaxed text-slate-600 dark:text-slate-300 sm:text-lg">
                                面向计算机专业学生的岗位化 AI 模拟面试系统，支持多轮动态追问、
                                多维能力评估与个性化提升建议，形成练习-评估-提升的闭环。
                            </p>

                            <div className="mt-8 flex flex-wrap items-center gap-4">
                                <button
                                    onClick={handleStartInterview}
                                    className="group inline-flex items-center gap-2 rounded-xl bg-cyan-700 px-6 py-3 text-lg font-bold text-white shadow-xl shadow-cyan-800/30 transition hover:-translate-y-0.5 hover:bg-cyan-800"
                                >
                                    <Radar className="h-5 w-5" />
                                    开始 AI 模拟面试
                                    <ArrowRight className="h-5 w-5 transition group-hover:translate-x-1" />
                                </button>

                                <button
                                    onClick={handleViewInsights}
                                    className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white/80 px-6 py-3 text-lg font-semibold text-slate-700 shadow-lg transition hover:-translate-y-0.5 hover:border-slate-400 hover:bg-white dark:border-slate-600 dark:bg-slate-900/60 dark:text-slate-200"
                                >
                                    <FileText className="h-5 w-5" />
                                    查看成长报告
                                </button>
                            </div>
                        </div>

                        <div className="grid gap-4">
                            <div className="rounded-2xl border border-cyan-200/60 bg-white/70 p-5 shadow-lg dark:border-cyan-900/60 dark:bg-slate-900/60">
                                <Activity className="mb-3 h-8 w-8 text-cyan-700 dark:text-cyan-300" />
                                <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">岗位化题库</h3>
                                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">覆盖技术题、项目深挖题、场景题与行为题，支持不同岗位切换。</p>
                            </div>

                            <div className="rounded-2xl border border-orange-200/60 bg-white/70 p-5 shadow-lg dark:border-orange-900/60 dark:bg-slate-900/60">
                                <Radar className="mb-3 h-8 w-8 text-orange-600 dark:text-orange-300" />
                                <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">动态追问链路</h3>
                                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">基于回答质量自动深入追问，模拟真实面试官的节奏控制与深挖策略。</p>
                            </div>

                            <div className="rounded-2xl border border-emerald-200/60 bg-white/70 p-5 shadow-lg dark:border-emerald-900/60 dark:bg-slate-900/60">
                                <FileText className="mb-3 h-8 w-8 text-emerald-600 dark:text-emerald-300" />
                                <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">多维成长报告</h3>
                                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">输出技术、逻辑、表达等维度评分与改进计划，支持长期成长追踪。</p>
                            </div>
                        </div>
                    </div>
                </section>

                <footer className="mt-8 px-2 text-center text-sm text-slate-500 dark:text-slate-400">
                    <p>天枢智面 2026 · AI 模拟面试与能力提升平台</p>
                </footer>
            </div>
        </main>
    )
}

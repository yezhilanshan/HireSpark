'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Briefcase, Code, Building2, User, ArrowLeft, ChevronRight } from 'lucide-react'

const INTERVIEW_ROUNDS = [
    {
        id: 'technical',
        name: '技术基础面',
        description: '考察基础知识、编码能力、语言特性、框架原理',
        icon: Code,
        color: 'from-blue-500 to-cyan-500'
    },
    {
        id: 'project',
        name: '项目深度面',
        description: '考察项目经验、技术深度、问题解决能力',
        icon: Building2,
        color: 'from-purple-500 to-pink-500'
    },
    {
        id: 'system_design',
        name: '系统设计面',
        description: '考察架构能力、全局思维、技术权衡能力',
        icon: Briefcase,
        color: 'from-orange-500 to-red-500'
    },
    {
        id: 'hr',
        name: 'HR 综合面',
        description: '考察软技能、文化匹配、职业规划',
        icon: User,
        color: 'from-green-500 to-teal-500'
    }
]

const POSITIONS = [
    { id: 'java_backend', name: 'Java 后端工程师' },
    { id: 'frontend', name: '前端工程师' },
    { id: 'fullstack', name: '全栈工程师' },
    { id: 'data_engineer', name: '数据工程师' },
    { id: 'devops', name: 'DevOps 工程师' },
    { id: 'algorithm', name: '算法工程师' }
]

const DIFFICULTY_LEVELS = [
    { id: 'easy', name: '简单', description: '适合初级/应届生' },
    { id: 'medium', name: '中等', description: '适合 1-3 年经验' },
    { id: 'hard', name: '困难', description: '适合 3 年以上经验' }
]

export default function InterviewSetupPage() {
    const router = useRouter()
    const [selectedRound, setSelectedRound] = useState<string>('technical')
    const [selectedPosition, setSelectedPosition] = useState<string>('java_backend')
    const [selectedDifficulty, setSelectedDifficulty] = useState<string>('medium')
    const [isStarting, setIsStarting] = useState(false)

    const handleStartInterview = () => {
        setIsStarting(true)
        // 存储面试配置到 sessionStorage
        sessionStorage.setItem('interview_config', JSON.stringify({
            round: selectedRound,
            position: selectedPosition,
            difficulty: selectedDifficulty
        }))
        // 跳转到面试页面
        setTimeout(() => {
            router.push('/interview')
        }, 500)
    }

    const currentRound = INTERVIEW_ROUNDS.find(r => r.id === selectedRound)
    const RoundIcon = currentRound?.icon || Code

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 dark:from-gray-900 dark:via-gray-900 dark:to-indigo-950 p-4 sm:p-8">
            <div className="max-w-5xl mx-auto">
                {/* Header */}
                <div className="mb-8">
                    <Link
                        href="/"
                        className="inline-flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 mb-4"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        返回首页
                    </Link>
                    <h1 className="text-3xl sm:text-4xl font-black text-gray-900 dark:text-white">
                        面试配置
                    </h1>
                    <p className="mt-2 text-gray-600 dark:text-gray-400">
                        选择面试轮次、职位和难度，开始模拟面试
                    </p>
                </div>

                {/* 面试轮次选择 */}
                <section className="mb-8">
                    <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4">
                        面试轮次
                    </h2>
                    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {INTERVIEW_ROUNDS.map((round) => {
                            const Icon = round.icon
                            const isSelected = selectedRound === round.id
                            return (
                                <button
                                    key={round.id}
                                    onClick={() => setSelectedRound(round.id)}
                                    className={`relative p-4 rounded-2xl border-2 transition-all duration-300 text-left ${
                                        isSelected
                                            ? `border-${round.color.split('-')[1]}-500 bg-gradient-to-br ${round.color} text-white shadow-xl scale-105`
                                            : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:border-gray-300 dark:hover:border-gray-600'
                                    }`}
                                >
                                    <div className="flex items-center gap-3 mb-2">
                                        <Icon className={`w-6 h-6 ${isSelected ? 'text-white' : 'text-gray-500 dark:text-gray-400'}`} />
                                        <span className={`font-bold ${isSelected ? 'text-white' : 'text-gray-900 dark:text-white'}`}>
                                            {round.name}
                                        </span>
                                    </div>
                                    <p className={`text-xs ${isSelected ? 'text-white/90' : 'text-gray-500 dark:text-gray-400'}`}>
                                        {round.description}
                                    </p>
                                    {isSelected && (
                                        <div className="absolute top-2 right-2">
                                            <div className="w-5 h-5 bg-white rounded-full flex items-center justify-center">
                                                <div className={`w-3 h-3 bg-gradient-to-br ${round.color} rounded-full`} />
                                            </div>
                                        </div>
                                    )}
                                </button>
                            )
                        })}
                    </div>
                </section>

                {/* 职位选择 */}
                <section className="mb-8">
                    <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4">
                        面试职位
                    </h2>
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {POSITIONS.map((position) => (
                            <button
                                key={position.id}
                                onClick={() => setSelectedPosition(position.id)}
                                className={`p-4 rounded-xl border-2 transition-all duration-200 text-left ${
                                    selectedPosition === position.id
                                        ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20'
                                        : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:border-gray-300 dark:hover:border-gray-600'
                                }`}
                            >
                                <span className={`font-semibold ${
                                    selectedPosition === position.id
                                        ? 'text-indigo-600 dark:text-indigo-400'
                                        : 'text-gray-900 dark:text-white'
                                }`}>
                                    {position.name}
                                </span>
                            </button>
                        ))}
                    </div>
                </section>

                {/* 难度选择 */}
                <section className="mb-8">
                    <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4">
                        面试难度
                    </h2>
                    <div className="grid sm:grid-cols-3 gap-3">
                        {DIFFICULTY_LEVELS.map((level) => (
                            <button
                                key={level.id}
                                onClick={() => setSelectedDifficulty(level.id)}
                                className={`p-4 rounded-xl border-2 transition-all duration-200 text-left ${
                                    selectedDifficulty === level.id
                                        ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20'
                                        : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:border-gray-300 dark:hover:border-gray-600'
                                }`}
                            >
                                <div className="flex items-center justify-between mb-1">
                                    <span className={`font-semibold ${
                                        selectedDifficulty === level.id
                                            ? 'text-indigo-600 dark:text-indigo-400'
                                            : 'text-gray-900 dark:text-white'
                                    }`}>
                                        {level.name}
                                    </span>
                                    {selectedDifficulty === level.id && (
                                        <div className="w-5 h-5 bg-indigo-500 rounded-full flex items-center justify-center">
                                            <div className="w-2 h-2 bg-white rounded-full" />
                                        </div>
                                    )}
                                </div>
                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                    {level.description}
                                </p>
                            </button>
                        ))}
                    </div>
                </section>

                {/* 配置总结 */}
                <section className="mb-8 p-6 rounded-2xl bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-900 border border-gray-200 dark:border-gray-700 shadow-lg">
                    <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">面试配置总结</h3>
                    <div className="space-y-3">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center">
                                <RoundIcon className="w-5 h-5 text-white" />
                            </div>
                            <div>
                                <p className="text-sm text-gray-500 dark:text-gray-400">面试轮次</p>
                                <p className="font-semibold text-gray-900 dark:text-white">{currentRound?.name}</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
                                <Building2 className="w-5 h-5 text-white" />
                            </div>
                            <div>
                                <p className="text-sm text-gray-500 dark:text-gray-400">面试职位</p>
                                <p className="font-semibold text-gray-900 dark:text-white">
                                    {POSITIONS.find(p => p.id === selectedPosition)?.name}
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-green-500 to-teal-500 flex items-center justify-center">
                                <span className="text-white font-bold text-sm">
                                    {DIFFICULTY_LEVELS.find(d => d.id === selectedDifficulty)?.name}
                                </span>
                            </div>
                            <div>
                                <p className="text-sm text-gray-500 dark:text-gray-400">面试难度</p>
                                <p className="font-semibold text-gray-900 dark:text-white">
                                    {DIFFICULTY_LEVELS.find(d => d.id === selectedDifficulty)?.description}
                                </p>
                            </div>
                        </div>
                    </div>
                </section>

                {/* 开始按钮 */}
                <div className="flex justify-center">
                    <button
                        onClick={handleStartInterview}
                        disabled={isStarting}
                        className="group relative inline-flex items-center gap-3 bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-600 hover:from-indigo-700 hover:via-purple-700 hover:to-indigo-700 text-white font-bold py-4 px-12 rounded-2xl transition-all duration-300 transform hover:scale-105 shadow-2xl hover:shadow-indigo-500/50 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none overflow-hidden"
                    >
                        <span className="relative z-10 flex items-center gap-3 text-lg">
                            {isStarting ? (
                                <>
                                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                    正在启动...
                                </>
                            ) : (
                                <>
                                    开始面试
                                    <ChevronRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                                </>
                            )}
                        </span>
                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent transform -skew-x-12 translate-x-full group-hover:translate-x-[-200%] transition-transform duration-1000" />
                    </button>
                </div>
            </div>
        </div>
    )
}

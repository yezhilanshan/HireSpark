'use client'

import dynamic from 'next/dynamic'
import { useMemo } from 'react'
import {
    AlertTriangle,
    Brain,
    CheckCircle2,
    Network,
    RefreshCcw,
    Target,
} from 'lucide-react'
import PersistentSidebar from '@/components/PersistentSidebar'
import { useTheme } from '@/components/ThemeProvider'
import DetailPanel from '@/components/knowledge-graph/DetailPanel'
import RiskPanel from '@/components/knowledge-graph/RiskPanel'
import StrengthPanel from '@/components/knowledge-graph/StrengthPanel'
import { useKnowledgeGraphData } from '@/components/knowledge-graph/useKnowledgeGraphData'

const KnowledgeGraphCanvas = dynamic(
    () => import('@/components/knowledge-graph/KnowledgeGraphCanvas'),
    { ssr: false }
)

export default function KnowledgeGraphPage() {
    const { resolvedTheme } = useTheme()
    const isDarkMode = resolvedTheme === 'dark'

    const {
        loading,
        refreshing,
        error,
        summary,
        selectedNode,
        relatedNodes,
        graphVisibleNodes,
        graphVisibleEdges,
        setSelectedNodeId,
        refreshGraph,
    } = useKnowledgeGraphData()

    const graphStats = useMemo(
        () => [
            {
                label: '图谱节点',
                value: summary.graph_node_count ?? graphVisibleNodes.length,
                icon: Brain,
            },
            {
                label: '稳定优势',
                value: summary.strength_count ?? 0,
                icon: CheckCircle2,
            },
            {
                label: '近期短板',
                value: summary.risk_count ?? 0,
                icon: AlertTriangle,
            },
            {
                label: '训练任务',
                value: summary.active_task_count ?? 0,
                icon: Target,
            },
        ],
        [graphVisibleNodes, summary]
    )

    const graphLegend = [
        { label: '知识/能力', color: 'bg-[#5B8BF7] dark:bg-[#B4BEFE]' },
        { label: '项目经验', color: 'bg-[#E6956F] dark:bg-[#F5C2E7]' },
        { label: '风险项', color: 'bg-[#E57A51] dark:bg-[#F38BA8]' },
        { label: '训练任务', color: 'bg-[#73A16E] dark:bg-[#94E2D5]' },
        { label: '用户/简历', color: 'bg-[#96A2B4] dark:bg-[#A6ADC8]' },
    ]

    return (
        <div className="flex min-h-screen bg-[#F6F2EB] dark:bg-[#0C1017]">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="min-h-screen px-5 py-6 text-[#1D1D1B] dark:text-[#EEF2F8] sm:px-6 lg:px-8">
                    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-6">
                        <section className="rounded-[34px] border border-[#E5DED0] bg-white/88 p-6 shadow-[0_18px_60px_rgba(17,17,17,0.06)] backdrop-blur sm:p-8 dark:border-[#283140] dark:bg-[#10151E]/90 dark:shadow-[0_18px_60px_rgba(0,0,0,0.28)]">
                            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                                <div className="space-y-3">
                                    <div className="inline-flex items-center gap-2 rounded-full border border-[#EAE2D5] bg-[#FBF7F0] px-3 py-1 text-xs font-semibold tracking-[0.18em] text-[#8B6F3D] dark:border-[#3A4658] dark:bg-[#141A23] dark:text-[#D6C7A6]">
                                        <Network className="h-3.5 w-3.5" />
                                        KNOWLEDGE GRAPH
                                    </div>
                                    <div className="space-y-2">
                                        <h1 className="font-serif text-4xl tracking-tight text-[#171717] dark:text-white">
                                            知识图谱总览
                                        </h1>
                                    </div>
                                </div>

                                <div className="flex flex-col items-start gap-3 lg:items-end">
                                    <div className="text-sm text-[#666257] dark:text-[#B8C2D3]">
                                        目标岗位
                                        <span className="ml-2 font-semibold text-[#171717] dark:text-white">
                                            {summary.target_position || '暂未设置'}
                                        </span>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => void refreshGraph(true)}
                                        disabled={refreshing}
                                        className="inline-flex items-center gap-2 rounded-2xl border border-[#DDD2BE] bg-[#FBF7F0] px-4 py-2 text-sm font-medium text-[#5B4B2E] transition hover:bg-[#F6EFDF] disabled:cursor-not-allowed disabled:opacity-60 dark:border-[#364253] dark:bg-[#151D29] dark:text-[#E3D3B0] dark:hover:bg-[#1A2432]"
                                    >
                                        <RefreshCcw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
                                        {refreshing ? '正在刷新图谱' : '刷新数据'}
                                    </button>
                                </div>
                            </div>
                        </section>

                        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                            {graphStats.map((item) => {
                                const Icon = item.icon
                                return (
                                    <div
                                        key={item.label}
                                        className="rounded-[28px] border border-[#E5DED0] bg-white/88 p-5 shadow-[0_14px_40px_rgba(17,17,17,0.05)] backdrop-blur dark:border-[#283140] dark:bg-[#10151E]/90"
                                    >
                                        <div className="flex items-center justify-between">
                                            <div className="space-y-1">
                                                <div className="text-sm text-[#7B756A] dark:text-[#B8C2D3]">
                                                    {item.label}
                                                </div>
                                                <div className="text-3xl font-semibold text-[#171717] dark:text-white">
                                                    {item.value}
                                                </div>
                                            </div>
                                            <div className="rounded-2xl border border-[#EEE6D7] bg-[#FBF7F0] p-3 text-[#8B6F3D] dark:border-[#334155] dark:bg-[#151D29] dark:text-[#D6C7A6]">
                                                <Icon className="h-5 w-5" />
                                            </div>
                                        </div>
                                    </div>
                                )
                            })}
                        </section>

                        <section className="rounded-[34px] border border-[#E5DED0] bg-[#FBF8F2] p-4 shadow-[0_14px_36px_rgba(17,17,17,0.04)] sm:p-6 dark:border-[#283140] dark:bg-[#0F141D]">
                            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 px-1">
                                <div>
                                    <h2 className="font-serif text-2xl text-[#171717] dark:text-white">
                                        Knowledge Graph
                                    </h2>
                                    <p className="mt-1 text-sm text-[#6D675D] dark:text-[#B8C2D3]">
                                        点击节点查看详情，结合下方信息面板快速定位优势、短板与最近证据。
                                    </p>
                                </div>
                                <div className="flex flex-wrap items-center gap-2 text-xs text-[#756E64] dark:text-[#B8C2D3]">
                                    {graphLegend.map((item) => (
                                        <span
                                            key={item.label}
                                            className="inline-flex items-center gap-2 rounded-full border border-[#E7DDC7] bg-[#FBF7F0] px-3 py-1 dark:border-[#334155] dark:bg-[#141B25]"
                                        >
                                            <span className={`h-2.5 w-2.5 rounded-full ${item.color}`} />
                                            {item.label}
                                        </span>
                                    ))}
                                </div>
                            </div>

                            {loading ? (
                                <div className="flex h-[680px] items-center justify-center rounded-[28px] border border-dashed border-[#DDD2BE] bg-[#FBF8F2] text-sm text-[#756E64] dark:border-[#334155] dark:bg-[#111823] dark:text-[#B8C2D3]">
                                    正在加载知识图谱...
                                </div>
                            ) : error ? (
                                <div className="flex h-[680px] items-center justify-center rounded-[28px] border border-dashed border-red-200 bg-red-50 px-6 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-300">
                                    {error}
                                </div>
                            ) : (
                                <KnowledgeGraphCanvas
                                    nodes={graphVisibleNodes}
                                    edges={graphVisibleEdges}
                                    selectedNodeId={selectedNode?.id || ''}
                                    isDarkMode={isDarkMode}
                                    onSelectNode={setSelectedNodeId}
                                />
                            )}
                        </section>

                        <section className="space-y-6">
                            <DetailPanel
                                selectedNode={selectedNode}
                                relatedNodes={relatedNodes}
                                visibleNodes={graphVisibleNodes}
                                onSelectNode={setSelectedNodeId}
                            />

                            <div className="grid gap-6 xl:grid-cols-2">
                                <StrengthPanel
                                    items={(summary.top_strengths || []).slice(0, 6)}
                                    onSelectNode={setSelectedNodeId}
                                />
                                <RiskPanel
                                    items={(summary.top_risks || []).slice(0, 6)}
                                    onSelectNode={setSelectedNodeId}
                                />
                            </div>
                        </section>
                    </div>
                </div>
            </main>
        </div>
    )
}

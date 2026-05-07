import { Sparkles } from 'lucide-react'
import { formatScore, getNodeTypeLabel, getStatusTone, getSuggestedNodes } from './helpers'
import type { GraphNode } from './types'

type DetailPanelProps = {
    selectedNode: GraphNode | null
    relatedNodes: GraphNode[]
    visibleNodes: GraphNode[]
    onSelectNode: (nodeId: string) => void
}

function renderMetaValue(value: unknown) {
    if (Array.isArray(value)) return value.join('、')
    if (typeof value === 'object' && value !== null) return JSON.stringify(value)
    return String(value)
}

export default function DetailPanel({
    selectedNode,
    relatedNodes,
    visibleNodes,
    onSelectNode,
}: DetailPanelProps) {
    return (
        <section className="rounded-[30px] border border-[#E5DED0] bg-white/88 p-6 shadow-[0_14px_40px_rgba(17,17,17,0.05)] backdrop-blur dark:border-[#283140] dark:bg-[#10151E]/90">
            <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-[#8B6F3D] dark:text-[#D6C7A6]" />
                    <h3 className="font-serif text-2xl text-[#171717] dark:text-white">知识点详情</h3>
                </div>
                {selectedNode ? (
                    <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${getStatusTone(selectedNode.status)}`}>
                        {getNodeTypeLabel(selectedNode.type)}
                    </span>
                ) : null}
            </div>

            {selectedNode ? (
                <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_280px]">
                    <div className="space-y-4">
                        <div className="rounded-[24px] border border-[#EEE4D4] bg-[#FBF7F0] p-5 dark:border-[#334155] dark:bg-[#141B25]">
                            <div className="flex flex-wrap items-start justify-between gap-3">
                                <div>
                                    <h4 className="text-2xl font-semibold text-[#171717] dark:text-white">
                                        {selectedNode.label}
                                    </h4>
                                    <p className="mt-2 text-sm leading-7 text-[#686258] dark:text-[#B8C2D3]">
                                        {selectedNode.description || '这个知识点目前还没有补充详细说明。'}
                                    </p>
                                </div>
                                {typeof selectedNode.score === 'number' ? (
                                    <div className="rounded-2xl border border-[#E5DED0] bg-white px-4 py-3 text-right dark:border-[#2E3948] dark:bg-[#101722]">
                                        <div className="text-xs uppercase tracking-[0.14em] text-[#9B9487] dark:text-[#8EA0B7]">
                                            当前评分
                                        </div>
                                        <div className="mt-1 text-2xl font-semibold text-[#171717] dark:text-white">
                                            {formatScore(selectedNode.score)}
                                        </div>
                                    </div>
                                ) : null}
                            </div>
                        </div>

                        {selectedNode.meta && Object.keys(selectedNode.meta).length > 0 ? (
                            <div className="rounded-[24px] border border-[#EEE4D4] bg-[#FBF7F0] p-5 dark:border-[#334155] dark:bg-[#141B25]">
                                <div className="mb-4 text-sm font-medium text-[#5F5545] dark:text-[#D6C7A6]">
                                    结构化信息
                                </div>
                                <div className="grid gap-3 sm:grid-cols-2">
                                    {Object.entries(selectedNode.meta).map(([key, value]) => (
                                        <div
                                            key={key}
                                            className="rounded-2xl border border-[#EFE6D9] bg-white/80 px-4 py-3 text-sm text-[#5F5A52] dark:border-[#2E3948] dark:bg-[#101722] dark:text-[#C7D1DF]"
                                        >
                                            <div className="text-xs uppercase tracking-[0.14em] text-[#9B9487] dark:text-[#8EA0B7]">
                                                {key}
                                            </div>
                                            <div className="mt-2 break-words leading-6">
                                                {renderMetaValue(value)}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : null}
                    </div>

                    <div className="space-y-4">
                        <div className="rounded-[24px] border border-[#EEE4D4] bg-[#FBF7F0] p-5 dark:border-[#334155] dark:bg-[#141B25]">
                            <div className="text-sm font-medium text-[#5F5545] dark:text-[#D6C7A6]">当前信息</div>
                            <div className="mt-4 space-y-3 text-sm text-[#5F5A52] dark:text-[#C7D1DF]">
                                <div className="flex items-center justify-between rounded-2xl bg-white/80 px-4 py-3 dark:bg-[#101722]">
                                    <span>类型</span>
                                    <span className="font-semibold text-[#171717] dark:text-white">
                                        {getNodeTypeLabel(selectedNode.type)}
                                    </span>
                                </div>
                                <div className="flex items-center justify-between rounded-2xl bg-white/80 px-4 py-3 dark:bg-[#101722]">
                                    <span>分组</span>
                                    <span className="font-semibold text-[#171717] dark:text-white">
                                        {selectedNode.group || '--'}
                                    </span>
                                </div>
                                <div className="flex items-center justify-between rounded-2xl bg-white/80 px-4 py-3 dark:bg-[#101722]">
                                    <span>状态</span>
                                    <span className="font-semibold text-[#171717] dark:text-white">
                                        {selectedNode.status || '--'}
                                    </span>
                                </div>
                            </div>
                        </div>

                        <div className="rounded-[24px] border border-[#EEE4D4] bg-[#FBF7F0] p-5 dark:border-[#334155] dark:bg-[#141B25]">
                            <div className="text-sm font-medium text-[#5F5545] dark:text-[#D6C7A6]">当前关联</div>
                            {relatedNodes.length ? (
                                <div className="mt-4 flex flex-wrap gap-2">
                                    {relatedNodes.map((node) => (
                                        <button
                                            key={node.id}
                                            type="button"
                                            onClick={() => onSelectNode(node.id)}
                                            className="rounded-full border border-[#E5DED0] bg-white px-3 py-2 text-sm text-[#5F5A52] transition hover:bg-[#F6EFDF] dark:border-[#334155] dark:bg-[#101722] dark:text-[#C7D1DF] dark:hover:bg-[#162130]"
                                        >
                                            {node.label}
                                        </button>
                                    ))}
                                </div>
                            ) : (
                                <p className="mt-4 text-sm leading-7 text-[#686258] dark:text-[#B8C2D3]">
                                    这个节点当前没有可展示的直接关联，你可以从优势或短板列表继续查看相邻知识点。
                                </p>
                            )}
                        </div>
                    </div>
                </div>
            ) : (
                <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
                    <div className="rounded-[24px] border border-dashed border-[#DDD2BE] bg-[#FBF8F2] p-6 dark:border-[#334155] dark:bg-[#111823]">
                        <p className="text-sm leading-7 text-[#756E64] dark:text-[#B8C2D3]">
                            点击图谱中的任意节点，可以查看对应知识点说明、结构化信息和关联内容。右侧两个面板则会帮助你快速判断哪些能力已经稳定，哪些还需要重点补强。
                        </p>
                    </div>
                    <div className="rounded-[24px] border border-[#EEE4D4] bg-[#FBF7F0] p-5 dark:border-[#334155] dark:bg-[#141B25]">
                        <div className="text-sm font-medium text-[#5F5545] dark:text-[#D6C7A6]">推荐先看</div>
                        <div className="mt-4 flex flex-wrap gap-2">
                            {getSuggestedNodes(visibleNodes).map((node) => (
                                <button
                                    key={node.id}
                                    type="button"
                                    onClick={() => onSelectNode(node.id)}
                                    className="rounded-full border border-[#E5DED0] bg-white px-3 py-2 text-sm text-[#5F5A52] transition hover:bg-[#F6EFDF] dark:border-[#334155] dark:bg-[#101722] dark:text-[#C7D1DF] dark:hover:bg-[#162130]"
                                >
                                    {node.label}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </section>
    )
}

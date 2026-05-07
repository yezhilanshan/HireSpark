import { AlertTriangle } from 'lucide-react'
import { formatScore } from './helpers'
import type { GraphNode } from './types'

type RiskPanelProps = {
    items: GraphNode[]
    onSelectNode: (nodeId: string) => void
}

export default function RiskPanel({ items, onSelectNode }: RiskPanelProps) {
    return (
        <section className="rounded-[30px] border border-[#E5DED0] bg-white/88 p-6 shadow-[0_14px_40px_rgba(17,17,17,0.05)] backdrop-blur dark:border-[#283140] dark:bg-[#10151E]/90">
            <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-orange-600 dark:text-orange-300" />
                <h3 className="font-serif text-2xl text-[#171717] dark:text-white">近期短板</h3>
            </div>
            <p className="mt-2 text-sm leading-7 text-[#6D675D] dark:text-[#B8C2D3]">
                优先级更高的补强项会集中放在这里，方便你直接规划下一轮训练任务。
            </p>
            <div className="mt-5 space-y-3">
                {items.map((node) => (
                    <button
                        type="button"
                        key={node.id}
                        onClick={() => onSelectNode(node.id)}
                        className="flex w-full items-center justify-between rounded-[22px] border border-orange-200 bg-orange-50 px-4 py-4 text-left text-sm text-orange-700 transition hover:bg-orange-100 dark:border-orange-800/60 dark:bg-orange-950/30 dark:text-orange-300 dark:hover:bg-orange-950/50"
                    >
                        <span>{node.label}</span>
                        <span className="font-semibold">{formatScore(node.score)}</span>
                    </button>
                ))}
                {!items.length ? (
                    <div className="rounded-[22px] border border-dashed border-[#F0D1B5] bg-[#FFF7F0] px-4 py-5 text-sm text-[#9C6434] dark:border-orange-900/40 dark:bg-orange-950/10 dark:text-orange-300">
                        暂时没有显著的高风险短板，保持训练节奏即可。
                    </div>
                ) : null}
            </div>
        </section>
    )
}

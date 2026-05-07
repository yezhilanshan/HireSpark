import { CheckCircle2 } from 'lucide-react'
import { formatScore } from './helpers'
import type { GraphNode } from './types'

type StrengthPanelProps = {
    items: GraphNode[]
    onSelectNode: (nodeId: string) => void
}

export default function StrengthPanel({ items, onSelectNode }: StrengthPanelProps) {
    return (
        <section className="rounded-[30px] border border-[#E5DED0] bg-white/88 p-6 shadow-[0_14px_40px_rgba(17,17,17,0.05)] backdrop-blur dark:border-[#283140] dark:bg-[#10151E]/90">
            <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-300" />
                <h3 className="font-serif text-2xl text-[#171717] dark:text-white">稳定优势</h3>
            </div>
            <p className="mt-2 text-sm leading-7 text-[#6D675D] dark:text-[#B8C2D3]">
                这里汇总当前表现最稳定、最适合继续放大的能力点。
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
                {items.map((node) => (
                    <button
                        type="button"
                        key={node.id}
                        onClick={() => onSelectNode(node.id)}
                        className="rounded-[22px] border border-emerald-200 bg-emerald-50 px-4 py-4 text-left text-sm text-emerald-700 transition hover:bg-emerald-100 dark:border-emerald-800/60 dark:bg-emerald-950/30 dark:text-emerald-300 dark:hover:bg-emerald-950/50"
                    >
                        <div className="font-medium">{node.label}</div>
                        <div className="mt-2 text-xs opacity-80">评分 {formatScore(node.score)}</div>
                    </button>
                ))}
                {!items.length ? (
                    <div className="sm:col-span-2 rounded-[22px] border border-dashed border-[#D8E6DE] bg-[#F5FBF7] px-4 py-5 text-sm text-[#5E7A68] dark:border-emerald-900/40 dark:bg-emerald-950/10 dark:text-emerald-300">
                        当前还没有形成明显的稳定优势，建议先从近期得分更高、反馈更一致的知识点开始复盘。
                    </div>
                ) : null}
            </div>
        </section>
    )
}

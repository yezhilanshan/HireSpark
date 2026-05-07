import { Brain } from 'lucide-react'
import { formatScore } from './helpers'
import type { RecentInterview } from './types'

type EvidencePanelProps = {
    items: RecentInterview[]
}

function getRiskTone(riskLevel?: string) {
    const normalized = String(riskLevel || '').toUpperCase()
    if (normalized === 'HIGH') {
        return 'border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-800/60 dark:bg-orange-950/30 dark:text-orange-300'
    }
    if (normalized === 'LOW') {
        return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800/60 dark:bg-emerald-950/30 dark:text-emerald-300'
    }
    return 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300'
}

export default function EvidencePanel({ items }: EvidencePanelProps) {
    return (
        <section className="rounded-[30px] border border-[#E5DED0] bg-white/88 p-6 shadow-[0_14px_40px_rgba(17,17,17,0.05)] backdrop-blur dark:border-[#283140] dark:bg-[#10151E]/90">
            <div className="flex items-center gap-2">
                <Brain className="h-5 w-5 text-sky-600 dark:text-sky-300" />
                <h3 className="font-serif text-2xl text-[#171717] dark:text-white">最近证据</h3>
            </div>
            <p className="mt-2 text-sm leading-7 text-[#6D675D] dark:text-[#B8C2D3]">
                最近几次项目或面试记录会在这里汇总，帮助你判断当前结论是否有足够的新证据支撑。
            </p>
            <div className="mt-5 grid gap-3 lg:grid-cols-2">
                {items.map((item) => (
                    <article
                        key={`${item.interview_id}-${item.time}`}
                        className="rounded-[22px] border border-[#EEE4D4] bg-[#FBF7F0] px-4 py-4 text-sm text-[#5F5A52] dark:border-[#334155] dark:bg-[#141B25] dark:text-[#C7D1DF]"
                    >
                        <div className="flex items-start justify-between gap-3">
                            <div className="font-medium text-[#1F1F1D] dark:text-white">{item.round_type}</div>
                            <div className="text-xs text-[#8B8476] dark:text-[#93A4B9]">{item.time || '--'}</div>
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
                            <span className="rounded-full border border-[#E5DED0] bg-white px-2.5 py-1 text-[#6D675D] dark:border-[#2E3948] dark:bg-[#101722] dark:text-[#B8C2D3]">
                                得分 {formatScore(item.score)}
                            </span>
                            <span className={`rounded-full border px-2.5 py-1 ${getRiskTone(item.risk_level)}`}>
                                风险 {item.risk_level || '--'}
                            </span>
                        </div>
                    </article>
                ))}
                {!items.length ? (
                    <div className="lg:col-span-2 rounded-[22px] border border-dashed border-[#DDD2BE] bg-[#FBF8F2] px-4 py-5 text-sm text-[#756E64] dark:border-[#334155] dark:bg-[#111823] dark:text-[#B8C2D3]">
                        暂时还没有最近证据，等新一轮面试或训练记录生成后会自动出现在这里。
                    </div>
                ) : null}
            </div>
        </section>
    )
}

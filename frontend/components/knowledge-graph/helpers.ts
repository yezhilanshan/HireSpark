import type { GraphNode } from './types'

export function formatScore(value?: number | null) {
    return Number.isFinite(Number(value)) ? Number(value).toFixed(1) : '--'
}

export function getNodeTypeLabel(type: string) {
    if (type === 'knowledge') return '知识点'
    if (type === 'capability') return '能力维度'
    if (type === 'project') return '项目经验'
    if (type === 'weakness') return '风险项'
    if (type === 'training') return '训练任务'
    if (type === 'user') return '用户'
    if (type === 'resume') return '简历'
    if (type === 'position') return '目标岗位'
    return '其他'
}

export function getStatusTone(status?: string | null) {
    if (status === 'mastered' || status === 'stable' || status === 'strength') {
        return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800/60 dark:bg-emerald-950/30 dark:text-emerald-300'
    }
    if (status === 'weak' || status === 'risk') {
        return 'border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-800/60 dark:bg-orange-950/30 dark:text-orange-300'
    }
    if (status === 'developing' || status === 'familiar') {
        return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-800/60 dark:bg-sky-950/30 dark:text-sky-300'
    }
    return 'border-[#E6DED0] bg-[#F8F5EE] text-[#6B655C] dark:border-[#2f3744] dark:bg-[#161b24] dark:text-[#C4CDD8]'
}

export function getSuggestedNodes(nodes: GraphNode[]) {
    return [...nodes]
        .sort((left, right) => {
            if (left.type === 'knowledge' && right.type !== 'knowledge') return -1
            if (left.type !== 'knowledge' && right.type === 'knowledge') return 1
            if (left.type === 'capability' && right.type !== 'capability') return -1
            if (left.type !== 'capability' && right.type === 'capability') return 1
            return (right.score || 0) - (left.score || 0)
        })
        .slice(0, 8)
}

'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { getBackendBaseUrl } from '@/lib/backend'
import type { GraphEdge, GraphNode, GraphPayload, GraphSummary } from './types'

const BACKEND_API_BASE = getBackendBaseUrl()
const KNOWLEDGE_GRAPH_REFRESH_KEY = 'zhiyuexingchen:knowledge-graph:refresh'

export function useKnowledgeGraphData() {
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)
    const [error, setError] = useState('')
    const [summary, setSummary] = useState<GraphSummary>({})
    const [nodes, setNodes] = useState<GraphNode[]>([])
    const [edges, setEdges] = useState<GraphEdge[]>([])
    const [selectedNodeId, setSelectedNodeId] = useState('')

    const refreshGraph = useCallback(async (isManual = false) => {
        if (isManual) setRefreshing(true)
        else setLoading(true)
        setError('')

        try {
            const response = await fetch(`${BACKEND_API_BASE}/api/knowledge-graph/profile`)
            const payload = (await response.json()) as GraphPayload

            if (!response.ok || !payload.success) {
                throw new Error(payload.error || '知识图谱加载失败')
            }

            const nextNodes = Array.isArray(payload.nodes) ? payload.nodes : []
            const visibleNodes = nextNodes.filter(
                (node) => node.type === 'knowledge' || node.type === 'project'
            )

            setSummary(payload.summary || {})
            setNodes(nextNodes)
            setEdges(Array.isArray(payload.edges) ? payload.edges : [])
            setSelectedNodeId((previous) => {
                if (previous && visibleNodes.some((node) => node.id === previous)) {
                    return previous
                }
                return visibleNodes.find((node) => node.type === 'knowledge')?.id || visibleNodes[0]?.id || ''
            })
        } catch (err) {
            setError(err instanceof Error ? err.message : '知识图谱加载失败')
        } finally {
            setLoading(false)
            setRefreshing(false)
        }
    }, [])

    useEffect(() => {
        void refreshGraph()
    }, [refreshGraph])

    useEffect(() => {
        const handleStorage = (event: StorageEvent) => {
            if (event.key !== KNOWLEDGE_GRAPH_REFRESH_KEY || !event.newValue) return
            void refreshGraph(true)
        }

        window.addEventListener('storage', handleStorage)
        return () => window.removeEventListener('storage', handleStorage)
    }, [refreshGraph])

    const graphVisibleNodes = useMemo(
        () => nodes.filter((node) => node.type === 'knowledge' || node.type === 'project'),
        [nodes]
    )

    const graphVisibleNodeIds = useMemo(
        () => new Set(graphVisibleNodes.map((node) => node.id)),
        [graphVisibleNodes]
    )

    const graphVisibleEdges = useMemo(
        () => edges.filter((edge) => graphVisibleNodeIds.has(edge.source) && graphVisibleNodeIds.has(edge.target)),
        [edges, graphVisibleNodeIds]
    )

    const selectedNode = useMemo(
        () => graphVisibleNodes.find((node) => node.id === selectedNodeId) || null,
        [graphVisibleNodes, selectedNodeId]
    )

    const relatedNodes = useMemo(() => {
        if (!selectedNodeId) return []

        const linkedIds = new Set<string>()
        graphVisibleEdges.forEach((edge) => {
            if (edge.source === selectedNodeId) linkedIds.add(edge.target)
            if (edge.target === selectedNodeId) linkedIds.add(edge.source)
        })

        return graphVisibleNodes.filter((node) => linkedIds.has(node.id)).slice(0, 6)
    }, [graphVisibleEdges, graphVisibleNodes, selectedNodeId])

    return {
        loading,
        refreshing,
        error,
        summary,
        nodes,
        edges,
        selectedNodeId,
        selectedNode,
        relatedNodes,
        graphVisibleNodes,
        graphVisibleEdges,
        setSelectedNodeId,
        refreshGraph,
    }
}

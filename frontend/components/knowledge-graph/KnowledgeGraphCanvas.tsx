'use client'

import { useEffect, useMemo, useRef } from 'react'
import * as d3drag from 'd3-drag'
import * as d3force from 'd3-force'
import * as d3sel from 'd3-selection'
import * as d3zoom from 'd3-zoom'
import { Move, RefreshCcw } from 'lucide-react'
import type { GraphEdge, GraphNode } from './types'

type Props = {
    nodes: GraphNode[]
    edges: GraphEdge[]
    selectedNodeId: string
    isDarkMode: boolean
    onSelectNode: (nodeId: string) => void
}

type ForceNode = d3force.SimulationNodeDatum & {
    id: string
    label: string
    type: string
    group: string
    status?: string | null
    score?: number | null
    description?: string
    title: string
    degree: number
    x?: number
    y?: number
    vx?: number
    vy?: number
    fx?: number | null
    fy?: number | null
}

type ForceEdge = d3force.SimulationLinkDatum<ForceNode> & {
    id: string
    source: string | ForceNode
    target: string | ForceNode
    label?: string
    type?: string
}

type GraphController = {
    fit: () => void
    reset: () => void
    setSelected: (nodeId: string) => void
    destroy: () => void
}

function sanitizeGroup(group: string) {
    const value = String(group || '').trim().toLowerCase()
    if (['knowledge', 'skill', 'concepts', 'capability'].includes(value)) return 'knowledge'
    if (['project', 'entities'].includes(value)) return 'project'
    if (['weakness', 'risk'].includes(value)) return 'weakness'
    if (['training', 'task', 'summaries'].includes(value)) return 'training'
    return 'other'
}

function nodeRadius(node: ForceNode) {
    if (node.type === 'knowledge') return 10 + Math.sqrt(Math.max(node.degree, 1)) * 2.8
    if (node.type === 'capability') return 12 + Math.sqrt(Math.max(node.degree, 1)) * 2.2
    if (node.type === 'weakness') return 13
    if (node.type === 'project') return 12
    if (node.type === 'training') return 11
    return 10
}

function buildGraphController(params: {
    svgElement: SVGSVGElement
    data: { nodes: GraphNode[]; edges: GraphEdge[] }
    isDarkMode: boolean
    selectedNodeId: string
    onNodeClick: (nodeId: string) => void
    onCanvasClick: () => void
}): GraphController {
    const { svgElement, data, isDarkMode, selectedNodeId, onNodeClick, onCanvasClick } = params
    const svg = d3sel.select(svgElement)
    svg.selectAll('*').remove()

    const width = svgElement.clientWidth || 1200
    const height = svgElement.clientHeight || 720
    svg.attr('viewBox', `0 0 ${width} ${height}`)

    svg
        .append('defs')
        .append('filter')
        .attr('id', 'zhiyuexingchen-node-glow')
        .attr('x', '-50%')
        .attr('y', '-50%')
        .attr('width', '200%')
        .attr('height', '200%')
        .append('feGaussianBlur')
        .attr('stdDeviation', 2)

    const root = svg.append('g').attr('class', 'graph-root')
    const linkLayer = root.append('g').attr('class', 'links')
    const nodeLayer = root.append('g').attr('class', 'nodes')

    const degreeMap = new Map<string, number>()
    data.nodes.forEach((node) => degreeMap.set(node.id, 0))
    data.edges.forEach((edge) => {
        degreeMap.set(edge.source, (degreeMap.get(edge.source) || 0) + 1)
        degreeMap.set(edge.target, (degreeMap.get(edge.target) || 0) + 1)
    })

    const nodes: ForceNode[] = data.nodes.map((node) => ({
        ...node,
        degree: degreeMap.get(node.id) || 0,
        title: node.label,
    }))
    const links: ForceEdge[] = data.edges.map((edge) => ({ ...edge }))

    for (const node of nodes) {
        const angle = Math.random() * Math.PI * 2
        const radius = 40 + Math.random() * 28
        node.x = width / 2 + Math.cos(angle) * radius
        node.y = height / 2 + Math.sin(angle) * radius
    }

    const adjacency = new Map<string, Set<string>>()
    for (const node of nodes) adjacency.set(node.id, new Set())
    for (const edge of data.edges) {
        adjacency.get(edge.source)?.add(edge.target)
        adjacency.get(edge.target)?.add(edge.source)
    }
    let currentSelectedId = selectedNodeId

    const simulation = d3force
        .forceSimulation<ForceNode>(nodes)
        .force(
            'link',
            d3force
                .forceLink<ForceNode, ForceEdge>(links)
                .id((node) => node.id)
                .distance((edge) => {
                    const source = edge.source as ForceNode
                    const target = edge.target as ForceNode
                    if (source.type === 'knowledge' && target.type === 'knowledge') return 170
                    if (source.type === 'weakness' || target.type === 'weakness') return 148
                    return 160
                })
                .strength(0.22)
        )
        .force('charge', d3force.forceManyBody<ForceNode>().strength(-650).distanceMax(900))
        .force('center', d3force.forceCenter(width / 2, height / 2))
        .force(
            'collision',
            d3force.forceCollide<ForceNode>().radius((node) => nodeRadius(node) + 14).strength(0.9)
        )
        .force('x', d3force.forceX(width / 2).strength(0.02))
        .force('y', d3force.forceY(height / 2).strength(0.02))
        .alphaDecay(0.005)
        .velocityDecay(0.28)
        .alphaTarget(0.015)

    simulation.force('noise', () => {
        for (const node of nodes) {
            if (node.fx != null) continue
            node.vx = (node.vx ?? 0) + (Math.random() - 0.5) * 0.09
            node.vy = (node.vy ?? 0) + (Math.random() - 0.5) * 0.09
        }
    })

    const linkSelection = linkLayer
        .selectAll<SVGPathElement, ForceEdge>('path')
        .data(links)
        .enter()
        .append('path')
        .attr('class', 'kg-link')
        .attr('fill', 'none')
        .attr('stroke-linecap', 'round')

    const nodeSelection = nodeLayer
        .selectAll<SVGGElement, ForceNode>('g.node')
        .data(nodes)
        .enter()
        .append('g')
        .attr('class', (node) => `kg-node group-${sanitizeGroup(node.group)}${node.degree >= 5 ? ' big' : ''}`)

    const nodeInner = nodeSelection
        .append('g')
        .attr('class', 'node-inner')
        .style('animation-delay', (_node, index) => `${Math.min(900, index * 18)}ms`)

    nodeInner
        .append('circle')
        .attr('class', 'node-halo')
        .attr('r', (node) => nodeRadius(node) * 1.3)
        .attr('filter', 'url(#zhiyuexingchen-node-glow)')

    nodeInner
        .append('circle')
        .attr('class', 'node-main')
        .attr('r', (node) => nodeRadius(node))

    nodeInner
        .append('text')
        .attr('class', 'node-label')
        .attr('dy', (node) => -nodeRadius(node) - 8)
        .attr('text-anchor', 'middle')
        .text((node) => node.title)

    nodeInner
        .filter((node) => typeof node.score === 'number')
        .append('text')
        .attr('class', 'node-score')
        .attr('dy', (node) => nodeRadius(node) + 13)
        .attr('text-anchor', 'middle')
        .text((node) => Number(node.score).toFixed(1))

    const dragBehavior = d3drag
        .drag<SVGGElement, ForceNode>()
        .on('start', (event, node) => {
            if (!event.active) simulation.alphaTarget(0.15).restart()
            node.fx = node.x
            node.fy = node.y
        })
        .on('drag', (event, node) => {
            node.fx = event.x
            node.fy = event.y
        })
        .on('end', (event, node) => {
            if (!event.active) simulation.alphaTarget(0.015)
            node.fx = null
            node.fy = null
        })
    nodeSelection.call(dragBehavior)

    const zoomBehavior = d3zoom
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.2, 4])
        .on('zoom', (event) => {
            root.attr('transform', event.transform.toString())
        })
    svg.call(zoomBehavior)

    const clearHighlight = () => {
        nodeSelection.classed('dim', false).classed('highlight', false).classed('selected', false)
        linkSelection.classed('dim', false).classed('highlight', false)
    }

    const applyHighlight = (focusId: string) => {
        const neighbors = adjacency.get(focusId) ?? new Set<string>()
        nodeSelection
            .classed('selected', (node) => node.id === currentSelectedId)
            .classed('highlight', (node) => node.id === focusId || neighbors.has(node.id))
            .classed('dim', (node) => node.id !== focusId && !neighbors.has(node.id))

        linkSelection
            .classed('highlight', (edge) => {
                const sourceId = (edge.source as ForceNode).id
                const targetId = (edge.target as ForceNode).id
                return sourceId === focusId || targetId === focusId
            })
            .classed('dim', (edge) => {
                const sourceId = (edge.source as ForceNode).id
                const targetId = (edge.target as ForceNode).id
                return sourceId !== focusId && targetId !== focusId
            })
    }

    const setSelected = (nodeId: string) => {
        currentSelectedId = nodeId
        if (nodeId) {
            const neighbors = adjacency.get(nodeId) ?? new Set<string>()
            nodeSelection
                .classed('selected', (node) => node.id === nodeId)
                .classed('highlight', (node) => node.id === nodeId || neighbors.has(node.id))
                .classed('dim', (node) => node.id !== nodeId && !neighbors.has(node.id))

            linkSelection
                .classed('highlight', (edge) => {
                    const sourceId = (edge.source as ForceNode).id
                    const targetId = (edge.target as ForceNode).id
                    return sourceId === nodeId || targetId === nodeId
                })
                .classed('dim', (edge) => {
                    const sourceId = (edge.source as ForceNode).id
                    const targetId = (edge.target as ForceNode).id
                    return sourceId !== nodeId && targetId !== nodeId
                })
            return
        }

        clearHighlight()
    }

    nodeSelection
        .on('mouseenter', (_event, node) => {
            applyHighlight(node.id)
        })
        .on('mouseleave', () => {
            if (currentSelectedId) {
                applyHighlight(currentSelectedId)
            } else {
                clearHighlight()
            }
        })
        .on('click', (event, node) => {
            event.stopPropagation()
            onNodeClick(node.id)
        })

    svg.on('click', () => {
        onCanvasClick()
        clearHighlight()
    })

    simulation.on('tick', () => {
        linkSelection.attr('d', (edge) => {
            const source = edge.source as ForceNode
            const target = edge.target as ForceNode
            if (source.x == null || source.y == null || target.x == null || target.y == null) return ''
            const dx = target.x - source.x
            const dy = target.y - source.y
            const distance = Math.hypot(dx, dy)
            const radius = Math.max(distance * 1.8, 1)
            return `M${source.x},${source.y}A${radius},${radius} 0 0,1 ${target.x},${target.y}`
        })

        nodeSelection.attr('transform', (node) => `translate(${node.x},${node.y})`)
    })

    const fit = () => {
        if (!nodes.length) return
        const xs = nodes.map((node) => node.x ?? width / 2)
        const ys = nodes.map((node) => node.y ?? height / 2)
        const minX = Math.min(...xs)
        const maxX = Math.max(...xs)
        const minY = Math.min(...ys)
        const maxY = Math.max(...ys)
        const graphWidth = Math.max(maxX - minX, 1)
        const graphHeight = Math.max(maxY - minY, 1)
        const scale = Math.min((width * 0.74) / graphWidth, (height * 0.74) / graphHeight, 1.55)
        const translateX = width / 2 - ((minX + maxX) / 2) * scale
        const translateY = height / 2 - ((minY + maxY) / 2) * scale
        svg.call(zoomBehavior.transform, d3zoom.zoomIdentity.translate(translateX, translateY).scale(scale))
    }

    setSelected(selectedNodeId)

    return {
        fit,
        reset: () => {
            svg.call(zoomBehavior.transform, d3zoom.zoomIdentity)
            simulation.alpha(0.22).restart()
        },
        setSelected,
        destroy: () => {
            simulation.stop()
            svg.on('.zoom', null)
            svg.on('click', null)
            svg.selectAll('*').remove()
        },
    }
}

export default function KnowledgeGraphCanvas({
    nodes,
    edges,
    selectedNodeId,
    isDarkMode,
    onSelectNode,
}: Props) {
    const svgRef = useRef<SVGSVGElement | null>(null)
    const controllerRef = useRef<GraphController | null>(null)
    const selectedNodeIdRef = useRef(selectedNodeId)

    selectedNodeIdRef.current = selectedNodeId

    const graphData = useMemo(
        () => ({
            nodes,
            edges,
        }),
        [edges, nodes]
    )

    useEffect(() => {
        if (!svgRef.current) return

        controllerRef.current?.destroy()
        controllerRef.current = buildGraphController({
            svgElement: svgRef.current,
            data: graphData,
            isDarkMode,
            selectedNodeId: selectedNodeIdRef.current,
            onNodeClick: onSelectNode,
            onCanvasClick: () => onSelectNode(''),
        })

        const timer = window.setTimeout(() => {
            controllerRef.current?.fit()
        }, 220)

        return () => {
            window.clearTimeout(timer)
            controllerRef.current?.destroy()
            controllerRef.current = null
        }
    }, [graphData, isDarkMode, onSelectNode])

    useEffect(() => {
        controllerRef.current?.setSelected(selectedNodeId)
    }, [selectedNodeId])

    return (
        <>
            <div className="relative h-[680px] w-full overflow-hidden rounded-[28px] border border-[#DDD6C8] bg-[#FCFBF8] shadow-[0_16px_40px_rgba(17,17,17,0.05)] dark:border-[#303a4a] dark:bg-[#121821]">
                <svg
                    ref={svgRef}
                    className="absolute inset-0 h-full w-full"
                    role="img"
                    aria-label="知识图谱关系画布"
                />

                <div className="pointer-events-none absolute left-5 top-5 flex items-center gap-2 rounded-full border border-[#E7DDC7] bg-[#FFFDF9] px-3 py-1.5 text-xs font-medium text-[#5A6471] shadow-sm dark:border-[#3B4658] dark:bg-[#161E2A] dark:text-[#C6D2E0]">
                    <Move className="h-3.5 w-3.5" />
                    拖拽节点、滚轮缩放，点击节点查看详情
                </div>

                <button
                    type="button"
                    onClick={() => controllerRef.current?.reset()}
                    className="absolute right-5 top-5 inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-[#E7DDC7] bg-[#FFFDF9] text-[#4A5462] shadow-sm transition hover:bg-white dark:border-[#3B4658] dark:bg-[#161E2A] dark:text-[#E6EDF7] dark:hover:bg-[#1B2532]"
                    aria-label="重置知识图谱视角"
                >
                    <RefreshCcw className="h-4 w-4" />
                </button>
            </div>

            <style jsx global>{`
                .kg-link {
                    stroke: ${isDarkMode ? 'rgba(180, 190, 254, 0.22)' : 'rgba(101, 116, 139, 0.24)'};
                    stroke-width: 1.25px;
                    transition: stroke 160ms ease, opacity 160ms ease, stroke-width 160ms ease;
                }

                .kg-link.highlight {
                    stroke: ${isDarkMode ? 'rgba(203, 166, 247, 0.72)' : 'rgba(91, 139, 247, 0.62)'};
                    stroke-width: 1.9px;
                    filter: drop-shadow(0 0 6px ${isDarkMode ? 'rgba(203,166,247,0.36)' : 'rgba(91,139,247,0.2)'});
                }

                .kg-link.dim {
                    opacity: 0.12;
                }

                .kg-node {
                    cursor: pointer;
                    transition: opacity 160ms ease;
                }

                .kg-node .node-inner {
                    animation: kg-node-fade-in 760ms cubic-bezier(0.22, 0.61, 0.36, 1) both;
                }

                .kg-node .node-halo {
                    opacity: 0.56;
                }

                .kg-node .node-main {
                    stroke-width: 1.5px;
                    transition: transform 160ms ease, stroke 160ms ease, fill 160ms ease;
                }

                .kg-node .node-label {
                    fill: ${isDarkMode ? '#ECF1FA' : '#233041'};
                    font-size: 12px;
                    font-weight: 600;
                    paint-order: stroke;
                    stroke: ${isDarkMode ? 'rgba(8,11,19,0.84)' : 'rgba(255,255,255,0.96)'};
                    stroke-width: 4px;
                    stroke-linejoin: round;
                }

                .kg-node .node-score {
                    fill: ${isDarkMode ? '#BECAE0' : '#617084'};
                    font-size: 11px;
                    font-weight: 500;
                    paint-order: stroke;
                    stroke: ${isDarkMode ? 'rgba(8,11,19,0.84)' : 'rgba(255,255,255,0.96)'};
                    stroke-width: 3px;
                    stroke-linejoin: round;
                }

                .kg-node.highlight .node-main,
                .kg-node:hover .node-main {
                    transform: scale(1.045);
                }

                .kg-node.selected .node-main {
                    stroke: ${isDarkMode ? '#F8FAFC' : '#111827'};
                    stroke-width: 2px;
                    filter: drop-shadow(0 0 10px ${isDarkMode ? 'rgba(255,255,255,0.2)' : 'rgba(17,24,39,0.14)'});
                }

                .kg-node.dim {
                    opacity: 0.18;
                }

                .kg-node.group-knowledge .node-main,
                .kg-node.group-knowledge .node-halo {
                    fill: ${isDarkMode ? '#B4BEFE' : '#5B8BF7'};
                    stroke: ${isDarkMode ? '#D9DFFF' : '#3C73E8'};
                }

                .kg-node.group-project .node-main,
                .kg-node.group-project .node-halo {
                    fill: ${isDarkMode ? '#F5C2E7' : '#E6956F'};
                    stroke: ${isDarkMode ? '#FFD9F2' : '#D67A45'};
                }

                .kg-node.group-weakness .node-main,
                .kg-node.group-weakness .node-halo {
                    fill: ${isDarkMode ? '#F38BA8' : '#E57A51'};
                    stroke: ${isDarkMode ? '#FFC0D0' : '#D9673B'};
                }

                .kg-node.group-training .node-main,
                .kg-node.group-training .node-halo {
                    fill: ${isDarkMode ? '#94E2D5' : '#73A16E'};
                    stroke: ${isDarkMode ? '#C8FFF3' : '#5D8D58'};
                }

                .kg-node.group-other .node-main,
                .kg-node.group-other .node-halo {
                    fill: ${isDarkMode ? '#A6ADC8' : '#96A2B4'};
                    stroke: ${isDarkMode ? '#D8DCF1' : '#7A8798'};
                }

                @keyframes kg-node-fade-in {
                    0% {
                        opacity: 0;
                        transform: translateY(10px) scale(0.92);
                    }
                    100% {
                        opacity: 1;
                        transform: translateY(0) scale(1);
                    }
                }
            `}</style>
        </>
    )
}

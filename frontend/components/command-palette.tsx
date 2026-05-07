'use client'

import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import {
    ArrowRight,
    BarChart3,
    BookOpen,
    Bot,
    Film,
    History,
    LayoutDashboard,
    LogOut,
    Network,
    Search,
    Settings,
} from 'lucide-react'
import { useRouter } from 'next/navigation'

type CommandItem = {
    id: string
    title: string
    icon: typeof Search
    href?: string
    section: string
    action?: 'logout'
}

const commands: CommandItem[] = [
    { id: 'dashboard', title: '主工作台', icon: LayoutDashboard, href: '/dashboard', section: '导航' },
    { id: 'questions', title: '题库浏览', icon: BookOpen, href: '/dashboard/questions', section: '导航' },
    { id: 'history', title: '面试记录', icon: History, href: '/history', section: '导航' },
    { id: 'replay', title: '面试复盘', icon: Film, href: '/replay', section: '导航' },
    { id: 'insights', title: '综合画像', icon: BarChart3, href: '/insights', section: '导航' },
    { id: 'knowledge-graph', title: '知识图谱', icon: Network, href: '/knowledge-graph', section: '导航' },
    { id: 'assistant', title: 'AI 问答助手', icon: Bot, href: '/assistant', section: '导航' },
    { id: 'start', title: '开始模拟面试', icon: ArrowRight, href: '/interview-setup', section: '快捷操作' },
    { id: 'settings', title: '设置', icon: Settings, href: '/settings', section: '系统' },
    { id: 'logout', title: '退出登录', icon: LogOut, section: '系统', action: 'logout' },
]

export function CommandPalette() {
    const router = useRouter()
    const [isOpen, setIsOpen] = useState(false)
    const [search, setSearch] = useState('')
    const [selectedIndex, setSelectedIndex] = useState(0)

    const filteredCommands = useMemo(
        () => commands.filter((cmd) => cmd.title.toLowerCase().includes(search.trim().toLowerCase())),
        [search]
    )

    useEffect(() => {
        const handleGlobalKeydown = (event: KeyboardEvent) => {
            const normalizedKey = typeof event.key === 'string' ? event.key.toLowerCase() : ''
            if (normalizedKey === 'k' && (event.metaKey || event.ctrlKey)) {
                event.preventDefault()
                setIsOpen((open) => !open)
            }
            if (event.key === 'Escape') {
                setIsOpen(false)
            }
        }

        document.addEventListener('keydown', handleGlobalKeydown)
        return () => document.removeEventListener('keydown', handleGlobalKeydown)
    }, [])

    useEffect(() => {
        setSelectedIndex(0)
    }, [search])

    const runCommand = async (command: CommandItem | undefined) => {
        if (!command) return
        setIsOpen(false)

        if (command.action === 'logout') {
            await fetch('/api/auth/logout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            }).catch(() => null)
            router.replace('/')
            router.refresh()
            return
        }

        if (command.href) {
            router.push(command.href)
        }
    }

    useEffect(() => {
        const handleListKeydown = (event: KeyboardEvent) => {
            if (!isOpen || filteredCommands.length === 0) return

            if (event.key === 'ArrowDown') {
                event.preventDefault()
                setSelectedIndex((prev) => (prev + 1) % filteredCommands.length)
            }

            if (event.key === 'ArrowUp') {
                event.preventDefault()
                setSelectedIndex((prev) => (prev - 1 + filteredCommands.length) % filteredCommands.length)
            }

            if (event.key === 'Enter') {
                event.preventDefault()
                void runCommand(filteredCommands[selectedIndex])
            }
        }

        document.addEventListener('keydown', handleListKeydown)
        return () => document.removeEventListener('keydown', handleListKeydown)
    }, [filteredCommands, isOpen, router, selectedIndex])

    return (
        <AnimatePresence>
            {isOpen ? (
                <>
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 bg-black/20 backdrop-blur-sm"
                        onClick={() => setIsOpen(false)}
                    />

                    <div className="pointer-events-none fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
                        <motion.div
                            initial={{ opacity: 0, scale: 0.96, y: -16 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.96, y: -16 }}
                            transition={{ type: 'spring', stiffness: 340, damping: 28 }}
                            className="pointer-events-auto w-full max-w-xl overflow-hidden rounded-3xl border border-[#E5E5E5] bg-white shadow-2xl"
                        >
                            <div className="flex items-center border-b border-[#E5E5E5] px-4 py-4">
                                <Search className="mr-3 h-5 w-5 text-[#999999]" />
                                <input
                                    autoFocus
                                    value={search}
                                    onChange={(event) => setSearch(event.target.value)}
                                    placeholder="搜索页面、功能或操作"
                                    className="flex-1 bg-transparent text-lg text-[#111111] outline-none placeholder:text-[#999999]"
                                />
                                <div className="rounded bg-[#F5F5F5] px-2 py-1 font-mono text-xs text-[#999999]">esc</div>
                            </div>

                            <div className="max-h-[60vh] overflow-y-auto p-2">
                                {filteredCommands.length === 0 ? (
                                    <div className="py-12 text-center text-sm text-[#666666]">没有找到匹配的操作</div>
                                ) : (
                                    <div className="space-y-1">
                                        {filteredCommands.map((command, index) => {
                                            const selected = index === selectedIndex
                                            return (
                                                <button
                                                    key={command.id}
                                                    type="button"
                                                    className={`flex w-full items-center rounded-2xl px-4 py-3 text-left transition-colors ${
                                                        selected ? 'bg-[#F5F5F5] text-[#111111]' : 'text-[#666666] hover:bg-[#FAFAFA]'
                                                    }`}
                                                    onMouseEnter={() => setSelectedIndex(index)}
                                                    onClick={() => void runCommand(command)}
                                                >
                                                    <command.icon className={`mr-3 h-5 w-5 ${selected ? 'text-[#111111]' : 'text-[#999999]'}`} />
                                                    <span className="font-medium">{command.title}</span>
                                                    <span className="ml-auto text-xs text-[#999999]">{command.section}</span>
                                                </button>
                                            )
                                        })}
                                    </div>
                                )}
                            </div>

                            <div className="flex items-center justify-between border-t border-[#E5E5E5] bg-[#FAFAFA] px-4 py-3 text-xs text-[#999999]">
                                <div className="flex items-center gap-4">
                                    <span className="flex items-center gap-1">
                                        <kbd className="rounded bg-[#E5E5E5] px-1.5 py-0.5 font-mono text-[#666666]">↑</kbd>
                                        <kbd className="rounded bg-[#E5E5E5] px-1.5 py-0.5 font-mono text-[#666666]">↓</kbd>
                                        切换
                                    </span>
                                    <span className="flex items-center gap-1">
                                        <kbd className="rounded bg-[#E5E5E5] px-1.5 py-0.5 font-mono text-[#666666]">enter</kbd>
                                        打开
                                    </span>
                                </div>
                                <div className="font-medium text-[#666666]">PanelMind</div>
                            </div>
                        </motion.div>
                    </div>
                </>
            ) : null}
        </AnimatePresence>
    )
}

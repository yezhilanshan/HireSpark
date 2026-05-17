'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
    Bot,
    Clock3,
    Loader2,
    MessageSquarePlus,
    PanelLeftClose,
    PanelLeftOpen,
    Send,
    Sparkles,
    Trash2,
    User,
} from 'lucide-react'
import PersistentSidebar from '@/components/PersistentSidebar'
import MarkdownMessage from '@/components/MarkdownMessage'
import { getBackendBaseUrl } from '@/lib/backend'
import { buildPageCacheKey, readPageCache, removePageCache, writePageCache } from '@/lib/page-cache'

const BACKEND_API_BASE = getBackendBaseUrl()
const ASSISTANT_TASK_POLL_INTERVAL_MS = 1200
const ASSISTANT_TASK_POLL_MAX_ATTEMPTS = 75
const ASSISTANT_SHELL_CACHE_KEY = 'zhiyuexingchen.page.assistant.shell.v1'
const ASSISTANT_MESSAGE_CACHE_PREFIX = 'zhiyuexingchen.page.assistant.messages.v1'
const ASSISTANT_CACHE_TTL_MS = 1000 * 60 * 15

type AssistantTask = {
    task_id: string
    status: 'queued' | 'running' | 'completed' | 'failed' | string
    stream_text?: string
    stream_version?: number
    stream_done?: boolean
    error?: {
        code?: string
        message?: string
    } | null
}

type Citation = {
    title: string
    source: string
    snippet: string
    score?: number | null
    source_type?: string
}

type Conversation = {
    conversation_id: string
    user_id: string
    title: string
    last_message_preview?: string
    updated_at?: string
    created_at?: string
    message_count?: number
}

type Message = {
    message_id: string
    conversation_id: string
    role: 'assistant' | 'user' | 'system'
    content: string
    answer_mode?: string
    citations?: Citation[]
}

type RagStatusState = {
    label: string
    description: string
    tone: string
}

type AssistantShellCacheData = {
    userId: string
    userName: string
    conversations: Conversation[]
    activeConversationId: string
    showConversationPanel: boolean
    ragStatus: RagStatusState
}

type AssistantMessagesCacheData = {
    messages: Message[]
}

function formatRelativeTime(value?: string) {
    if (!value) return '刚刚'
    const time = new Date(value).getTime()
    if (!Number.isFinite(time)) return value
    const diffMinutes = Math.max(0, Math.round((Date.now() - time) / 60000))
    if (diffMinutes < 1) return '刚刚'
    if (diffMinutes < 60) return `${diffMinutes} 分钟前`
    const diffHours = Math.round(diffMinutes / 60)
    if (diffHours < 24) return `${diffHours} 小时前`
    return `${Math.round(diffHours / 24)} 天前`
}

function answerModeMeta(mode?: string) {
    if (mode === 'rag_grounded') {
        return ['基于知识库', 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'] as const
    }
    if (mode === 'rag_plus_model') {
        return ['知识库 + 补充判断', 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'] as const
    }
    return ['知识库证据不足', 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'] as const
}

const SUGGESTED_PROMPTS = [
    '帮我梳理前端面试里怎么讲项目难点',
    '总结 Java 后端高频考点',
    '如何准备行为面试中的 STAR 回答',
    '数据结构与算法常见面试题有哪些',
]

export default function AssistantPage() {
    const initialShellCache = typeof window === 'undefined'
        ? null
        : readPageCache<AssistantShellCacheData>(ASSISTANT_SHELL_CACHE_KEY, ASSISTANT_CACHE_TTL_MS)
    const initialActiveConversationId = String(initialShellCache?.activeConversationId || '').trim()
    const initialMessageCacheKey = buildPageCacheKey(
        ASSISTANT_MESSAGE_CACHE_PREFIX,
        `${String(initialShellCache?.userId || 'default').trim().toLowerCase()}:${initialActiveConversationId}`
    )
    const initialMessagesCache = typeof window === 'undefined' || !initialActiveConversationId
        ? null
        : readPageCache<AssistantMessagesCacheData>(initialMessageCacheKey, ASSISTANT_CACHE_TTL_MS)

    const [userId, setUserId] = useState(String(initialShellCache?.userId || 'default').trim().toLowerCase() || 'default')
    const [userName, setUserName] = useState(String(initialShellCache?.userName || '职跃星辰 用户').trim() || '职跃星辰 用户')
    const [conversations, setConversations] = useState<Conversation[]>(initialShellCache?.conversations || [])
    const [activeConversationId, setActiveConversationId] = useState(initialActiveConversationId)
    const [messages, setMessages] = useState<Message[]>(initialMessagesCache?.messages || [])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(!initialShellCache)
    const [sending, setSending] = useState(false)
    const [sidebarLoading, setSidebarLoading] = useState(false)
    const [showConversationPanel, setShowConversationPanel] = useState(
        typeof initialShellCache?.showConversationPanel === 'boolean' ? initialShellCache.showConversationPanel : true
    )
    const [deletingConversationId, setDeletingConversationId] = useState('')
    const [error, setError] = useState('')
    const [lastPrompt, setLastPrompt] = useState('')
    const [ragStatus, setRagStatus] = useState<RagStatusState>(
        initialShellCache?.ragStatus || { label: '知识库检查中', description: '正在读取助手状态。', tone: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400' }
    )
    const bottomRef = useRef<HTMLDivElement | null>(null)
    const textareaRef = useRef<HTMLTextAreaElement | null>(null)

    const activeConversation = useMemo(
        () => conversations.find((item) => item.conversation_id === activeConversationId) || null,
        [activeConversationId, conversations]
    )

    const loadAuth = async () => {
        const response = await fetch('/api/auth/me', { cache: 'no-store' })
        const data = await response.json().catch(() => ({}))
        const nextUserId = String(data?.user?.email || 'default').trim().toLowerCase() || 'default'
        const nextUserName = String(data?.user?.name || '职跃星辰 用户').trim() || '职跃星辰 用户'
        setUserId(nextUserId)
        setUserName(nextUserName)
        return nextUserId
    }

    const loadHealth = async () => {
        const response = await fetch(`${BACKEND_API_BASE}/api/assistant/health`, { cache: 'no-store' })
        const data = await response.json().catch(() => ({}))
        const rag = data?.data?.rag
        if (rag?.enabled && rag?.dual_index_ready) {
            setRagStatus({
                label: '知识库在线',
                description: `当前可引用 ${Number(rag.count || 0)} 条知识片段`,
                tone: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
            })
            return
        }
        if (rag?.enabled) {
            setRagStatus({
                label: '知识库准备中',
                description: '',
                tone: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
            })
            return
        }
        setRagStatus({
            label: '知识库未启用',
            description: '当前回答会更多依赖模型补充。',
            tone: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
        })
    }

    const loadConversations = async (currentUserId: string, preferredId = '', preserveActive = false) => {
        setSidebarLoading(true)
        try {
            const response = await fetch(
                `${BACKEND_API_BASE}/api/assistant/conversations?user_id=${encodeURIComponent(currentUserId)}&limit=100`,
                { cache: 'no-store' }
            )
            const data = await response.json().catch(() => ({}))
            if (!response.ok || !data?.success) {
                throw new Error(data?.error || '加载会话列表失败。')
            }
            const nextConversations = Array.isArray(data?.conversations) ? data.conversations : []
            setConversations(nextConversations)

            if (preferredId && nextConversations.some((item: Conversation) => item.conversation_id === preferredId)) {
                setActiveConversationId(preferredId)
                return
            }
            if (preserveActive && activeConversationId && nextConversations.some((item: Conversation) => item.conversation_id === activeConversationId)) {
                return
            }
            setActiveConversationId(nextConversations[0]?.conversation_id || '')
        } finally {
            setSidebarLoading(false)
        }
    }

    const loadMessages = async (conversationId: string, currentUserId: string) => {
        if (!conversationId) {
            setMessages([])
            return
        }

        const messagesCacheKey = buildPageCacheKey(
            ASSISTANT_MESSAGE_CACHE_PREFIX,
            `${String(currentUserId || 'default').trim().toLowerCase()}:${conversationId}`
        )
        const cachedMessages = readPageCache<AssistantMessagesCacheData>(messagesCacheKey, ASSISTANT_CACHE_TTL_MS)
        if (cachedMessages?.messages?.length) {
            setMessages(cachedMessages.messages)
        }

        const response = await fetch(
            `${BACKEND_API_BASE}/api/assistant/conversations/${encodeURIComponent(conversationId)}?user_id=${encodeURIComponent(currentUserId)}`,
            { cache: 'no-store' }
        )
        const data = await response.json().catch(() => ({}))
        if (!response.ok || !data?.success) {
            throw new Error(data?.error || '加载会话失败。')
        }
        const nextMessages = Array.isArray(data?.messages) ? data.messages : []
        setMessages(nextMessages)
        writePageCache<AssistantMessagesCacheData>(messagesCacheKey, { messages: nextMessages })
    }

    const createConversation = async () => {
        const response = await fetch(`${BACKEND_API_BASE}/api/assistant/conversations`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId }),
        })
        const data = await response.json().catch(() => ({}))
        if (!response.ok || !data?.success || !data?.conversation?.conversation_id) {
            throw new Error(data?.error || '创建会话失败。')
        }
        const conversationId = String(data.conversation.conversation_id)
        await loadConversations(userId, conversationId)
        setMessages([])
        setActiveConversationId(conversationId)
        return conversationId
    }

    const deleteConversation = async (conversationId: string) => {
        const normalizedId = String(conversationId || '').trim()
        if (!normalizedId || deletingConversationId) return

        if (typeof window !== 'undefined') {
            const confirmed = window.confirm('确认删除这条历史会话吗？删除后将不再显示在列表中。')
            if (!confirmed) return
        }

        setDeletingConversationId(normalizedId)
        setError('')
        try {
            const response = await fetch(
                `${BACKEND_API_BASE}/api/assistant/conversations/${encodeURIComponent(normalizedId)}`,
                {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId }),
                }
            )
            const data = await response.json().catch(() => ({}))
            if (!response.ok || !data?.success) {
                throw new Error(data?.error || '删除会话失败。')
            }

            removePageCache(
                buildPageCacheKey(
                    ASSISTANT_MESSAGE_CACHE_PREFIX,
                    `${String(userId || 'default').trim().toLowerCase()}:${normalizedId}`
                )
            )

            const wasActive = activeConversationId === normalizedId
            await loadConversations(userId)
            if (wasActive) {
                setMessages([])
            }
        } catch (deleteError) {
            setError(deleteError instanceof Error ? deleteError.message : '删除会话失败。')
        } finally {
            setDeletingConversationId('')
        }
    }

    const patchPendingMessageContent = (pendingMessageId: string, content: string) => {
        setMessages((prev) =>
            prev.map((item) =>
                item.message_id === pendingMessageId
                    ? { ...item, content }
                    : item
            )
        )
    }

    const replacePendingMessage = (pendingMessageId: string, assistantMessage: Message) => {
        setMessages((prev) =>
            prev.map((item) => (item.message_id === pendingMessageId ? assistantMessage : item))
        )
    }

    const streamAssistantTask = (
        taskId: string,
        conversationId: string,
        currentUserId: string,
        pendingMessageId: string
    ) => {
        if (typeof window === 'undefined' || typeof window.EventSource === 'undefined') {
            return false
        }

        const streamUrl = `${BACKEND_API_BASE}/api/assistant/tasks/${encodeURIComponent(taskId)}/stream?user_id=${encodeURIComponent(currentUserId)}`
        let stream: EventSource
        try {
            stream = new EventSource(streamUrl)
        } catch {
            return false
        }

        let finished = false
        const closeStream = () => {
            try {
                stream.close()
            } catch {
                // ignore close errors
            }
        }

        const fallbackToPolling = () => {
            if (finished) return
            closeStream()
            void pollAssistantTask(taskId, conversationId, currentUserId, pendingMessageId)
        }

        const handlePayload = (rawPayload: unknown) => {
            const payload =
                rawPayload && typeof rawPayload === 'object'
                    ? (rawPayload as Record<string, unknown>)
                    : {}
            const task =
                payload.task && typeof payload.task === 'object'
                    ? (payload.task as AssistantTask)
                    : ({} as AssistantTask)

            const status = String(task.status || '').toLowerCase()
            const streamedText = String(task.stream_text || '').trim()
            if (streamedText) {
                patchPendingMessageContent(pendingMessageId, streamedText)
            }

            if (status === 'failed') {
                finished = true
                const failureMessage = String(
                    task.error?.message || '分析失败，请稍后重试。'
                )
                patchPendingMessageContent(pendingMessageId, `抱歉，这次分析失败：${failureMessage}`)
                setError(failureMessage)
                closeStream()
                return
            }

            if (status === 'completed') {
                finished = true
                const assistantMessage =
                    payload.assistant_message && typeof payload.assistant_message === 'object'
                        ? (payload.assistant_message as Message)
                        : undefined
                if (assistantMessage?.message_id) {
                    replacePendingMessage(pendingMessageId, assistantMessage)
                } else if (streamedText) {
                    patchPendingMessageContent(pendingMessageId, streamedText)
                } else {
                    void loadMessages(conversationId, currentUserId)
                }
                void loadConversations(currentUserId, conversationId, true)
                closeStream()
            }
        }

        stream.addEventListener('assistant_stream', (event) => {
            try {
                const parsed = JSON.parse((event as MessageEvent).data || '{}')
                handlePayload(parsed)
            } catch {
                // ignore malformed SSE payload
            }
        })

        stream.addEventListener('timeout', () => {
            fallbackToPolling()
        })

        stream.onerror = () => {
            fallbackToPolling()
        }

        return true
    }

    const pollAssistantTask = async (
        taskId: string,
        conversationId: string,
        currentUserId: string,
        pendingMessageId: string
    ) => {
        const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
        let attempts = 0
        while (attempts < ASSISTANT_TASK_POLL_MAX_ATTEMPTS) {
            await sleep(ASSISTANT_TASK_POLL_INTERVAL_MS)
            attempts += 1
            try {
                const response = await fetch(
                    `${BACKEND_API_BASE}/api/assistant/tasks/${encodeURIComponent(taskId)}?user_id=${encodeURIComponent(currentUserId)}`,
                    { cache: 'no-store' }
                )
                const data = await response.json().catch(() => ({}))
                if (!response.ok || !data?.success) {
                    continue
                }

                const task = (data?.task || {}) as AssistantTask
                const status = String(task?.status || '').toLowerCase()
                if (status === 'queued' || status === 'running') {
                    setMessages((prev) =>
                        prev.map((item) =>
                            item.message_id === pendingMessageId
                                ? { ...item, content: status === 'queued' ? '已接收，正在排队分析...' : '已接收，正在分析你的问题...' }
                                : item
                        )
                    )
                    continue
                }

                if (status === 'streaming') {
                    const streamText = String(task?.stream_text || '').trim()
                    if (streamText) {
                        patchPendingMessageContent(pendingMessageId, streamText)
                    }
                    continue
                }

                if (status === 'failed') {
                    const reason = String(task?.error?.message || '分析失败，请重试。')
                    setMessages((prev) =>
                        prev.map((item) =>
                            item.message_id === pendingMessageId
                                ? { ...item, content: `抱歉，这次分析失败：${reason}` }
                                : item
                        )
                    )
                    setError(reason)
                    return
                }

                if (status === 'completed') {
                    const assistantMessage = data?.assistant_message as Message | undefined
                    if (assistantMessage?.message_id) {
                        setMessages((prev) =>
                            prev.map((item) => (item.message_id === pendingMessageId ? assistantMessage : item))
                        )
                    } else if (String(task?.stream_text || '').trim()) {
                        patchPendingMessageContent(pendingMessageId, String(task?.stream_text || '').trim())
                    } else {
                        await loadMessages(conversationId, currentUserId)
                    }
                    await loadConversations(currentUserId, conversationId, true)
                    return
                }
            } catch {
                // ignore transient polling errors
            }
        }

        setMessages((prev) =>
            prev.map((item) =>
                item.message_id === pendingMessageId
                    ? { ...item, content: '分析超时，建议点击重试或重新提问。' }
                    : item
            )
        )
        setError('AI助手处理超时，请稍后重试。')
    }

    const sendMessage = async (overrideText?: string) => {
        const content = String(overrideText ?? input).trim()
        if (!content || sending) return

        const optimisticMessageId = `temp_${Date.now()}`
        setSending(true)
        setError('')
        setLastPrompt(content)

        try {
            let conversationId = activeConversationId
            if (!conversationId) {
                conversationId = await createConversation()
            }

            const optimisticMessage: Message = {
                message_id: optimisticMessageId,
                conversation_id: conversationId,
                role: 'user',
                content,
            }
            setMessages((prev) => [...prev, optimisticMessage])
            setInput('')

            const response = await fetch(
                `${BACKEND_API_BASE}/api/assistant/conversations/${encodeURIComponent(conversationId)}/messages`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: userId,
                        message: content,
                        temperature: 0.25,
                    }),
                }
            )
            const data = await response.json().catch(() => ({}))
            if (!response.ok || !data?.success) {
                throw new Error(data?.message || data?.error || '发送失败，请稍后重试。')
            }

            const userMessage = data?.user_message as Message | undefined
            const assistantMessage = data?.assistant_message as Message | undefined
            setMessages((prev) => {
                const withoutTemp = prev.filter((item) => item.message_id !== optimisticMessage.message_id)
                const next = [...withoutTemp]
                if (userMessage) next.push(userMessage)
                return next
            })
            await loadConversations(userId, conversationId, true)

            const isAsync = Boolean(data?.async)
            const taskId = String(data?.task?.task_id || '').trim()
            if (isAsync && taskId) {
                const pendingMessageId = `pending_${taskId}`
                const placeholderContent = String(data?.placeholder?.content || '已接收，正在分析你的问题...')
                setMessages((prev) => [
                    ...prev,
                    {
                        message_id: pendingMessageId,
                        conversation_id: conversationId,
                        role: 'assistant',
                        content: placeholderContent,
                    },
                ])
                const streamStarted = streamAssistantTask(taskId, conversationId, userId, pendingMessageId)
                if (!streamStarted) {
                    void pollAssistantTask(taskId, conversationId, userId, pendingMessageId)
                }
            } else if (assistantMessage) {
                setMessages((prev) => [...prev, assistantMessage])
            }
        } catch (sendError) {
            setMessages((prev) => prev.filter((item) => item.message_id !== optimisticMessageId))
            setError(sendError instanceof Error ? sendError.message : '发送失败，请稍后重试。')
        } finally {
            setSending(false)
        }
    }

    const adjustTextareaHeight = () => {
        const textarea = textareaRef.current
        if (!textarea) return
        textarea.style.height = 'auto'
        const maxHeight = 200
        textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`
    }

    useEffect(() => {
        const bootstrap = async () => {
            try {
                const currentUserId = await loadAuth()
                await Promise.all([loadHealth(), loadConversations(currentUserId)])
            } catch (bootstrapError) {
                setError(bootstrapError instanceof Error ? bootstrapError.message : '助手初始化失败。')
            } finally {
                setLoading(false)
            }
        }
        void bootstrap()
    }, [])

    useEffect(() => {
        if (!activeConversationId) {
            setMessages([])
            return
        }
        if (!userId) return
        void loadMessages(activeConversationId, userId).catch((detailError) => {
            setError(detailError instanceof Error ? detailError.message : '加载会话失败。')
        })
    }, [activeConversationId, userId])

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, sending])

    useEffect(() => {
        writePageCache<AssistantShellCacheData>(ASSISTANT_SHELL_CACHE_KEY, {
            userId,
            userName,
            conversations,
            activeConversationId,
            showConversationPanel,
            ragStatus,
        })
    }, [userId, userName, conversations, activeConversationId, showConversationPanel, ragStatus])

    useEffect(() => {
        const normalizedConversationId = String(activeConversationId || '').trim()
        if (!normalizedConversationId || messages.length === 0) return

        const messageCacheKey = buildPageCacheKey(
            ASSISTANT_MESSAGE_CACHE_PREFIX,
            `${String(userId || 'default').trim().toLowerCase()}:${normalizedConversationId}`
        )
        writePageCache<AssistantMessagesCacheData>(messageCacheKey, { messages })
    }, [userId, activeConversationId, messages])

    useEffect(() => {
        adjustTextareaHeight()
    }, [input])

    return (
        <div className="flex h-screen overflow-hidden bg-white dark:bg-[#0f0f0f]">
            <PersistentSidebar />

            {/* Conversation sidebar */}
            {showConversationPanel ? (
                <aside className="hidden w-[280px] shrink-0 flex-col border-r border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-[#171717] md:flex">
                    <div className="flex items-center justify-between px-4 py-3">
                        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">对话历史</h2>
                        <div className="flex items-center gap-1">
                            <button
                                type="button"
                                onClick={() => void createConversation().catch((e) => setError(e instanceof Error ? e.message : '创建会话失败。'))}
                                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-500 transition hover:bg-gray-200 dark:text-gray-400 dark:hover:bg-gray-700"
                                aria-label="新建对话"
                            >
                                <MessageSquarePlus className="h-4 w-4" />
                            </button>
                            <button
                                type="button"
                                onClick={() => setShowConversationPanel(false)}
                                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-500 transition hover:bg-gray-200 dark:text-gray-400 dark:hover:bg-gray-700"
                                aria-label="隐藏会话栏"
                            >
                                <PanelLeftClose className="h-4 w-4" />
                            </button>
                        </div>
                    </div>

                    <div className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
                        {loading || sidebarLoading ? (
                            <div className="flex items-center gap-2 px-3 py-8 text-sm text-gray-500 dark:text-gray-400">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                加载中...
                            </div>
                        ) : conversations.length === 0 ? (
                            <div className="px-3 py-8 text-center text-sm text-gray-400 dark:text-gray-500">
                                还没有对话记录
                            </div>
                        ) : (
                            conversations.map((conversation) => {
                                const active = conversation.conversation_id === activeConversationId
                                const deleting = deletingConversationId === conversation.conversation_id
                                return (
                                    <div
                                        key={conversation.conversation_id}
                                        className={`group relative flex items-center gap-2 rounded-xl px-3 py-2.5 transition cursor-pointer ${
                                            active
                                                ? 'bg-gray-200/70 dark:bg-gray-700/70'
                                                : 'hover:bg-gray-100 dark:hover:bg-gray-800/60'
                                        }`}
                                        onClick={() => setActiveConversationId(conversation.conversation_id)}
                                    >
                                        <div className="min-w-0 flex-1">
                                            <p className={`truncate text-sm ${active ? 'font-medium text-gray-900 dark:text-gray-100' : 'text-gray-700 dark:text-gray-300'}`}>
                                                {conversation.title}
                                            </p>
                                            <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">
                                                {formatRelativeTime(conversation.updated_at || conversation.created_at)}
                                            </p>
                                        </div>
                                        <button
                                            type="button"
                                            disabled={deleting}
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                void deleteConversation(conversation.conversation_id)
                                            }}
                                            className="hidden h-7 w-7 shrink-0 items-center justify-center rounded-lg text-gray-400 transition hover:bg-gray-200 hover:text-red-500 group-hover:inline-flex dark:hover:bg-gray-700 dark:hover:text-red-400"
                                            aria-label="删除会话"
                                        >
                                            {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                                        </button>
                                    </div>
                                )
                            })
                        )}
                    </div>

                    {/* RAG status */}
                    <div className="border-t border-gray-200 px-4 py-2.5 dark:border-gray-800">
                        <div className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${ragStatus.tone}`}>
                            <Sparkles className="h-3 w-3" />
                            <span>{ragStatus.label}</span>
                        </div>
                    </div>
                </aside>
            ) : null}

            {/* Main chat area */}
            <main className="flex flex-1 flex-col overflow-hidden">
                {/* Top bar */}
                <header className="flex h-12 shrink-0 items-center justify-between border-b border-gray-200 px-4 dark:border-gray-800">
                    <div className="flex items-center gap-2">
                        {!showConversationPanel ? (
                            <button
                                type="button"
                                onClick={() => setShowConversationPanel(true)}
                                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-500 transition hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
                                aria-label="显示会话栏"
                            >
                                <PanelLeftOpen className="h-4 w-4" />
                            </button>
                        ) : null}
                        <h1 className="text-sm font-medium text-gray-900 dark:text-gray-100">
                            {activeConversation?.title || 'AI 面试助手'}
                        </h1>
                    </div>
                    <button
                        type="button"
                        onClick={() => void createConversation().catch((e) => setError(e instanceof Error ? e.message : '创建会话失败。'))}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:bg-[#1a1a1a] dark:text-gray-300 dark:hover:bg-gray-800"
                    >
                        <MessageSquarePlus className="h-3.5 w-3.5" />
                        新对话
                    </button>
                </header>

                {/* Messages area */}
                <div className="flex-1 overflow-y-auto">
                    {loading ? (
                        <div className="flex h-full items-center justify-center">
                            <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                正在准备助手...
                            </div>
                        </div>
                    ) : messages.length === 0 ? (
                        /* Welcome screen */
                        <div className="flex h-full flex-col items-center justify-center px-4">
                            <div className="mx-auto max-w-2xl text-center">
                                <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-600 shadow-lg shadow-emerald-500/20">
                                    <Bot className="h-8 w-8 text-white" />
                                </div>
                                <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">
                                    你好，{userName}
                                </h2>
                                <p className="mt-2 text-base text-gray-500 dark:text-gray-400">
                                    我是你的 AI 面试助手，可以帮你梳理项目难点、总结高频考点、准备面试回答。
                                </p>

                                <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2">
                                    {SUGGESTED_PROMPTS.map((prompt) => (
                                        <button
                                            key={prompt}
                                            type="button"
                                            onClick={() => {
                                                setInput(prompt)
                                                textareaRef.current?.focus()
                                            }}
                                            className="rounded-xl border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-700 transition hover:border-gray-300 hover:bg-gray-50 dark:border-gray-700 dark:bg-[#1a1a1a] dark:text-gray-300 dark:hover:border-gray-600 dark:hover:bg-[#222]"
                                        >
                                            {prompt}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>
                    ) : (
                        /* Messages list */
                        <div className="mx-auto max-w-3xl px-4 py-6">
                            {messages.map((message) => {
                                const isAssistant = message.role === 'assistant'
                                const [modeLabel, modeTone] = isAssistant ? answerModeMeta(message.answer_mode) : ['', '']

                                return (
                                    <div key={message.message_id} className="mb-6 last:mb-0">
                                        <div className={`flex gap-3 ${isAssistant ? '' : 'flex-row-reverse'}`}>
                                            {/* Avatar */}
                                            <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                                                isAssistant
                                                    ? 'bg-gradient-to-br from-emerald-400 to-teal-600'
                                                    : 'bg-gray-900 dark:bg-gray-600'
                                            }`}>
                                                {isAssistant ? (
                                                    <Bot className="h-4 w-4 text-white" />
                                                ) : (
                                                    <User className="h-4 w-4 text-white" />
                                                )}
                                            </div>

                                            {/* Message content */}
                                            <div className={`min-w-0 flex-1 ${isAssistant ? '' : 'flex flex-col items-end'}`}>
                                                <p className={`mb-1 text-xs font-medium ${isAssistant ? 'text-gray-500 dark:text-gray-400' : 'text-gray-500 dark:text-gray-400'}`}>
                                                    {isAssistant ? 'AI 助手' : '你'}
                                                </p>

                                                <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-7 ${
                                                    isAssistant
                                                        ? 'bg-gray-100 text-gray-900 dark:bg-[#1e1e1e] dark:text-gray-100'
                                                        : 'bg-gray-900 text-white dark:bg-gray-700'
                                                }`}>
                                                    {isAssistant ? (
                                                        <MarkdownMessage content={message.content} className="text-inherit" />
                                                    ) : (
                                                        <div className="whitespace-pre-wrap">{message.content}</div>
                                                    )}
                                                </div>

                                                {/* Assistant metadata */}
                                                {isAssistant ? (
                                                    <div className="mt-2 flex flex-wrap items-center gap-2">
                                                        {modeLabel ? (
                                                            <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${modeTone}`}>
                                                                <Sparkles className="h-3 w-3" />
                                                                {modeLabel}
                                                            </span>
                                                        ) : null}
                                                    </div>
                                                ) : null}

                                                {/* Citations */}
                                                {isAssistant && Array.isArray(message.citations) && message.citations.length > 0 ? (
                                                    <div className="mt-3 space-y-2">
                                                        <p className="text-xs font-medium text-gray-500 dark:text-gray-400">参考来源</p>
                                                        <div className="grid gap-2 sm:grid-cols-2">
                                                            {message.citations.slice(0, 4).map((citation, index) => (
                                                                <div
                                                                    key={`${message.message_id}_${index}`}
                                                                    className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-[#1a1a1a]"
                                                                >
                                                                    <div className="flex items-start justify-between gap-2">
                                                                        <p className="text-xs font-medium text-gray-900 dark:text-gray-100">{citation.title}</p>
                                                                        {typeof citation.score === 'number' ? (
                                                                            <span className="shrink-0 rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-500 dark:bg-gray-800 dark:text-gray-400">
                                                                                {citation.score.toFixed(2)}
                                                                            </span>
                                                                        ) : null}
                                                                    </div>
                                                                    <p className="mt-0.5 text-[11px] text-gray-400 dark:text-gray-500">{citation.source}</p>
                                                                    <p className="mt-1.5 text-xs leading-5 text-gray-600 dark:text-gray-400 line-clamp-3">{citation.snippet}</p>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                ) : null}
                                            </div>
                                        </div>
                                    </div>
                                )
                            })}

                            {/* Sending indicator */}
                            {sending ? (
                                <div className="mb-6 flex gap-3">
                                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-emerald-400 to-teal-600">
                                        <Bot className="h-4 w-4 text-white" />
                                    </div>
                                    <div>
                                        <p className="mb-1 text-xs font-medium text-gray-500 dark:text-gray-400">AI 助手</p>
                                        <div className="inline-flex items-center gap-2 rounded-2xl bg-gray-100 px-4 py-3 dark:bg-[#1e1e1e]">
                                            <div className="flex gap-1">
                                                <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.3s] dark:bg-gray-500" />
                                                <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.15s] dark:bg-gray-500" />
                                                <span className="h-2 w-2 animate-bounce rounded-full bg-gray-400 dark:bg-gray-500" />
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            ) : null}

                            <div ref={bottomRef} />
                        </div>
                    )}
                </div>

                {/* Input area */}
                <div className="shrink-0 border-t border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-[#0f0f0f]">
                    <div className="mx-auto max-w-3xl">
                        {error ? (
                            <div className="mb-2 flex items-center justify-between rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-400">
                                <span className="text-xs">{error}</span>
                                {lastPrompt ? (
                                    <button
                                        type="button"
                                        onClick={() => void sendMessage(lastPrompt)}
                                        className="shrink-0 rounded-lg bg-red-100 px-2 py-1 text-xs font-medium text-red-700 transition hover:bg-red-200 dark:bg-red-900/40 dark:text-red-400 dark:hover:bg-red-900/60"
                                    >
                                        重试
                                    </button>
                                ) : null}
                            </div>
                        ) : null}

                        <div className="flex items-end gap-2 rounded-2xl border border-gray-200 bg-gray-50 px-3 py-2 transition focus-within:border-gray-400 dark:border-gray-700 dark:bg-[#1a1a1a] dark:focus-within:border-gray-500">
                            <textarea
                                ref={textareaRef}
                                value={input}
                                onChange={(event) => setInput(event.target.value)}
                                onKeyDown={(event) => {
                                    if (event.key === 'Enter' && !event.shiftKey) {
                                        event.preventDefault()
                                        void sendMessage()
                                    }
                                }}
                                rows={1}
                                placeholder="输入你的问题..."
                                className="max-h-[200px] min-h-[24px] flex-1 resize-none bg-transparent text-sm leading-6 text-gray-900 outline-none placeholder:text-gray-400 dark:text-gray-100 dark:placeholder:text-gray-500"
                            />
                            <button
                                type="button"
                                onClick={() => void sendMessage()}
                                disabled={!input.trim() || sending}
                                className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gray-900 text-white transition hover:bg-gray-700 disabled:cursor-not-allowed disabled:bg-gray-300 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-200 dark:disabled:bg-gray-700"
                                aria-label="发送消息"
                            >
                                {sending ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <Send className="h-4 w-4" />
                                )}
                            </button>
                        </div>

                        <p className="mt-2 text-center text-[11px] text-gray-400 dark:text-gray-500">
                            AI 助手基于知识库回答，内容仅供参考。支持 Shift+Enter 换行。
                        </p>
                    </div>
                </div>
            </main>
        </div>
    )
}

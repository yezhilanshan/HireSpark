'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
    Bot,
    ChevronRight,
    Clock3,
    Loader2,
    MessageSquarePlus,
    PanelLeftClose,
    PanelLeftOpen,
    RefreshCcw,
    Send,
    Sparkles,
    Trash2,
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
        return ['基于知识库', 'border-emerald-200 bg-emerald-50 text-emerald-700'] as const
    }
    if (mode === 'rag_plus_model') {
        return ['知识库 + 补充判断', 'border-amber-200 bg-amber-50 text-amber-700'] as const
    }
    return ['知识库证据不足', 'border-slate-200 bg-slate-100 text-slate-600'] as const
}

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
    const [userName, setUserName] = useState(String(initialShellCache?.userName || 'PanelMind 用户').trim() || 'PanelMind 用户')
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
        initialShellCache?.ragStatus || { label: '知识库检查中', description: '正在读取助手状态。', tone: 'border-slate-200 bg-slate-100 text-slate-600' }
    )
    const bottomRef = useRef<HTMLDivElement | null>(null)

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
                tone: 'border-emerald-200 bg-emerald-50 text-emerald-700',
            })
            return
        }
        if (rag?.enabled) {
            setRagStatus({
                label: '知识库准备中',
                description: '',
                tone: 'border-amber-200 bg-amber-50 text-amber-700',
            })
            return
        }
        setRagStatus({
            label: '知识库未启用',
            description: '当前回答会更多依赖模型补充。',
            tone: 'border-slate-200 bg-slate-100 text-slate-600',
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

    const sendMessageLegacy = async (overrideText?: string) => {
        const content = String(overrideText ?? input).trim()
        if (!content || sending) return

        setSending(true)
        setError('')
        setLastPrompt(content)

        try {
            let conversationId = activeConversationId
            if (!conversationId) {
                conversationId = await createConversation()
            }

            const optimisticMessage: Message = {
                message_id: `temp_${Date.now()}`,
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
                throw new Error(data?.message || data?.error || '发送消息失败。')
            }

            const userMessage = data?.user_message as Message | undefined
            const assistantMessage = data?.assistant_message as Message | undefined
            setMessages((prev) => {
                const withoutTemp = prev.filter((item) => item.message_id !== optimisticMessage.message_id)
                const next = [...withoutTemp]
                if (userMessage) next.push(userMessage)
                if (assistantMessage) next.push(assistantMessage)
                return next
            })
            await loadConversations(userId, conversationId, true)
        } catch (sendError) {
            setMessages((prev) => prev.filter((item) => !item.message_id.startsWith('temp_')))
            setError(sendError instanceof Error ? sendError.message : '发送消息失败。')
        } finally {
            setSending(false)
        }
    }

    void sendMessageLegacy

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

    return (
        <div className="flex min-h-screen bg-[#FAF9F6] dark:bg-[#101217]">
            <PersistentSidebar />
            <main className="flex-1 overflow-y-auto">
                <div className="mx-auto max-w-[1440px] px-6 py-8">
                    <section className="rounded-3xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] p-8 shadow-sm">
                        <div className="flex flex-wrap items-start justify-between gap-4">
                            <div>
                                <p className="text-xs font-medium uppercase tracking-[0.18em] text-[#999999] dark:text-[#8e98aa]">AI 问答助手</p>
                                <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#111111] dark:text-[#f4f7fb] sm:text-4xl">AI面试助手</h1>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    type="button"
                                    onClick={() => setShowConversationPanel((prev) => !prev)}
                                    className="inline-flex items-center gap-2 rounded-full border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] px-3 py-1.5 text-xs font-medium text-[#111111] dark:text-[#f4f7fb] transition hover:bg-[#F8F6F0] dark:hover:bg-[#2d3542]"
                                >
                                    {showConversationPanel ? <PanelLeftClose className="h-3.5 w-3.5" /> : <PanelLeftOpen className="h-3.5 w-3.5" />}
                                    <span>{showConversationPanel ? '隐藏会话栏' : '显示会话栏'}</span>
                                </button>
                                <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${ragStatus.tone}`}>
                                    <Sparkles className="h-3.5 w-3.5" />
                                    <span>{ragStatus.label}</span>
                                </div>
                            </div>
                        </div>
                        <p className="mt-3 text-xs leading-6 text-[#666666] dark:text-[#bcc5d3]">{ragStatus.description}</p>
                    </section>

                    <section className={`mt-6 grid gap-6 ${showConversationPanel ? 'grid-cols-1 md:grid-cols-[320px_minmax(0,1fr)]' : 'grid-cols-1'}`}>
                        {showConversationPanel ? (
                            <aside className="flex h-[calc(100vh-200px)] flex-col rounded-3xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-5 shadow-sm">
                                <div className="flex items-center justify-between gap-3">
                                    <div>
                                        <h2 className="text-lg font-semibold text-[#111111] dark:text-[#f4f7fb]">历史会话</h2>
                                        <p className="mt-1 text-xs leading-6 text-[#666666] dark:text-[#bcc5d3]">按当前登录用户保存。</p>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => void createConversation().catch((e) => setError(e instanceof Error ? e.message : '创建会话失败。'))}
                                        className="inline-flex items-center gap-2 rounded-xl border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] px-3 py-2 text-sm font-medium text-[#111111] dark:text-[#f4f7fb] transition hover:bg-[#F3F1EB] dark:hover:bg-[#2d3542]"
                                    >
                                        <MessageSquarePlus className="h-4 w-4" />
                                        新建
                                    </button>
                                </div>


                                <div className="mt-4 flex-1 space-y-2 overflow-y-auto min-h-0">
                                    {loading || sidebarLoading ? (
                                        <div className="flex items-center gap-2 rounded-2xl border border-dashed border-[#E5E5E5] dark:border-[#2d3542] px-4 py-5 text-sm text-[#666666] dark:text-[#bcc5d3]">
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                            加载会话列表中...
                                        </div>
                                    ) : conversations.length === 0 ? (
                                        <div className="rounded-2xl border border-dashed border-[#E5E5E5] dark:border-[#2d3542] px-4 py-6 text-sm leading-7 text-[#666666] dark:text-[#bcc5d3]">
                                            还没有历史会话。你可以先新建一个会话，向助手提问岗位准备、项目表达或知识点梳理。
                                        </div>
                                    ) : (
                                        conversations.map((conversation) => {
                                            const active = conversation.conversation_id === activeConversationId
                                            const deleting = deletingConversationId === conversation.conversation_id
                                            return (
                                                <div
                                                    key={conversation.conversation_id}
                                                    className={`w-full rounded-2xl border px-4 py-3 text-left transition ${active ? 'border-[#D9D1BC] bg-[#F7F2E6] shadow-sm' : 'border-[#EAE7DD] dark:border-[#2d3542] bg-[#FCFBF8] dark:bg-[#181c24] hover:border-[#DDD7C7] hover:bg-[#F8F5EE] dark:hover:border-[#2d3542] dark:hover:bg-[#2d3542]'
                                                        }`}
                                                >
                                                    <div className="flex items-start justify-between gap-3">
                                                        <button
                                                            type="button"
                                                            onClick={() => setActiveConversationId(conversation.conversation_id)}
                                                            className="min-w-0 flex-1 text-left"
                                                        >
                                                            <p className="truncate text-sm font-semibold text-[#111111] dark:text-[#f4f7fb]">{conversation.title}</p>
                                                            <p className="mt-1 line-clamp-2 text-xs leading-6 text-[#666666] dark:text-[#bcc5d3]">{conversation.last_message_preview || '还没有消息内容'}</p>
                                                        </button>
                                                        <button
                                                            type="button"
                                                            disabled={deleting}
                                                            onClick={() => void deleteConversation(conversation.conversation_id)}
                                                            className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-[#E5E5E5] dark:border-[#2d3542] text-[#999999] dark:text-[#8e98aa] transition hover:text-red-600 hover:border-red-200 disabled:cursor-not-allowed disabled:opacity-50"
                                                            aria-label="删除会话"
                                                        >
                                                            {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                                                        </button>
                                                        <ChevronRight className={`mt-0.5 h-4 w-4 shrink-0 ${active ? 'text-[#111111] dark:text-[#f4f7fb]' : 'text-[#999999] dark:text-[#8e98aa]'}`} />
                                                    </div>
                                                    <div className="mt-3 flex items-center gap-2 text-[11px] text-[#999999] dark:text-[#8e98aa]">
                                                        <Clock3 className="h-3.5 w-3.5" />
                                                        <span>{formatRelativeTime(conversation.updated_at || conversation.created_at)}</span>
                                                    </div>
                                                </div>
                                            )
                                        })
                                    )}
                                </div>
                            </aside>
                        ) : null}

                        <section className="overflow-hidden rounded-3xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] shadow-sm">
                            <div className="border-b border-[#EAE7DD] dark:border-[#2d3542] px-6 py-5">
                                <h2 className="text-xl font-semibold text-[#111111] dark:text-[#f4f7fb]">{activeConversation?.title || 'AI 问答助手'}</h2>
                                <p className="mt-1 text-sm leading-6 text-[#666666] dark:text-[#bcc5d3]">优先使用知识库回答求职问答、项目表达和岗位准备问题；证据不足时会明确标注。</p>
                            </div>

                            <div className="flex h-[68vh] min-h-[500px] max-h-[820px] flex-col sm:h-[72vh] sm:min-h-[620px]">
                                <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
                                    {loading ? (
                                        <div className="flex items-center gap-2 text-sm text-[#666666] dark:text-[#bcc5d3]">
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                            正在准备助手工作区...
                                        </div>
                                    ) : messages.length === 0 ? (
                                        <div className="flex min-h-[420px] items-center justify-center">
                                            <div className="max-w-xl rounded-3xl border border-dashed border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] px-8 py-10 text-center">
                                                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24]">
                                                    <Bot className="h-6 w-6 text-[#111111] dark:text-[#f4f7fb]" />
                                                </div>
                                                <h3 className="mt-5 text-xl font-semibold text-[#111111] dark:text-[#f4f7fb]">开始一段可追溯的 AI 对话</h3>
                                                <p className="mt-3 text-sm leading-7 text-[#666666] dark:text-[#bcc5d3]">
                                                    你可以直接问：帮我梳理前端面试里怎么讲项目难点，或者根据知识库总结 Java 后端高频考点。
                                                </p>
                                            </div>
                                        </div>
                                    ) : (
                                        messages.map((message) => {
                                            const isAssistant = message.role === 'assistant'
                                            const [modeLabel, modeTone] = answerModeMeta(message.answer_mode)
                                            return (
                                                <article key={message.message_id} className="space-y-3">
                                                    <div className={`flex ${isAssistant ? 'justify-start' : 'justify-end'}`}>
                                                        <div className={`max-w-4xl rounded-[28px] border px-5 py-4 text-sm leading-7 shadow-sm ${isAssistant ? 'border-[#E8E4D9] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#181c24] text-[#1A1A1A] dark:text-[#f4f7fb]' : 'border-[#111111] bg-[#111111] text-white'}`}>
                                                            <div className="mb-2 flex items-center gap-2 text-xs font-medium opacity-80">
                                                                {isAssistant ? <Bot className="h-3.5 w-3.5" /> : <span className="inline-block h-2 w-2 rounded-full bg-current" />}
                                                                <span>{isAssistant ? 'AI 助手' : '你'}</span>
                                                            </div>
                                                            {isAssistant ? (
                                                                <MarkdownMessage content={message.content} className="text-inherit" />
                                                            ) : (
                                                                <div className="whitespace-pre-wrap">{message.content}</div>
                                                            )}
                                                            {!isAssistant ? (
                                                                <button
                                                                    type="button"
                                                                    onClick={() => setInput(message.content)}
                                                                    className="mt-3 inline-flex items-center gap-2 rounded-full border border-white/20 px-3 py-1 text-xs text-white/80 transition hover:bg-white/10 hover:text-white"
                                                                >
                                                                    <RefreshCcw className="h-3 w-3" />
                                                                    再次提问
                                                                </button>
                                                            ) : null}
                                                        </div>
                                                    </div>

                                                    {isAssistant ? (
                                                        <div className="mr-auto max-w-4xl space-y-3">
                                                            <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${modeTone}`}>
                                                                <Sparkles className="h-3.5 w-3.5" />
                                                                <span>{modeLabel}</span>
                                                            </div>
                                                            {Array.isArray(message.citations) && message.citations.length > 0 ? (
                                                                <div className="grid gap-3 md:grid-cols-2">
                                                                    {message.citations.slice(0, 4).map((citation, index) => (
                                                                        <div key={`${message.message_id}_${index}`} className="rounded-2xl border border-[#EAE7DD] dark:border-[#2d3542] bg-white dark:bg-[#181c24] p-4">
                                                                            <div className="flex items-start justify-between gap-3">
                                                                                <div>
                                                                                    <p className="text-sm font-semibold text-[#111111] dark:text-[#f4f7fb]">{citation.title}</p>
                                                                                    <p className="mt-1 text-xs text-[#999999] dark:text-[#8e98aa]">{citation.source}</p>
                                                                                </div>
                                                                                {typeof citation.score === 'number' ? (
                                                                                    <span className="rounded-full bg-[#F5F1E8] px-2 py-1 text-[11px] font-medium text-[#8A6A35]">{citation.score.toFixed(2)}</span>
                                                                                ) : null}
                                                                            </div>
                                                                            <p className="mt-3 text-xs leading-6 text-[#666666] dark:text-[#bcc5d3]">{citation.snippet}</p>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            ) : null}
                                                        </div>
                                                    ) : null}
                                                </article>
                                            )
                                        })
                                    )}

                                    {sending ? (
                                        <div className="flex items-center gap-2 rounded-2xl border border-[#EAE7DD] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] px-4 py-3 text-sm text-[#666666] dark:text-[#bcc5d3]">
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                            正在基于知识库组织回答...
                                        </div>
                                    ) : null}
                                    <div ref={bottomRef} />
                                </div>

                                <div className="border-t border-[#EAE7DD] dark:border-[#2d3542] px-6 py-5">
                                    {error ? (
                                        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                            <span>{error}</span>
                                            {lastPrompt ? (
                                                <button
                                                    type="button"
                                                    onClick={() => void sendMessage(lastPrompt)}
                                                    className="inline-flex items-center gap-2 rounded-xl border border-red-200 bg-white px-3 py-2 text-sm font-medium text-red-700 transition hover:bg-red-50"
                                                >
                                                    <RefreshCcw className="h-4 w-4" />
                                                    重新发送
                                                </button>
                                            ) : null}
                                        </div>
                                    ) : null}

                                    <div className="rounded-[28px] border border-[#E5E5E5] dark:border-[#2d3542] bg-[#FAF9F6] dark:bg-[#101217] p-3">
                                        <textarea
                                            value={input}
                                            onChange={(event) => setInput(event.target.value)}
                                            onKeyDown={(event) => {
                                                if (event.key === 'Enter' && !event.shiftKey) {
                                                    event.preventDefault()
                                                    void sendMessage()
                                                }
                                            }}
                                            rows={3}
                                            placeholder="继续追问，或直接让助手基于知识库帮你梳理一个主题。"
                                            className="w-full resize-none bg-transparent px-3 py-2 text-sm leading-7 text-[#111111] dark:text-[#f4f7fb] outline-none placeholder:text-[#999999] dark:placeholder:text-[#8e98aa]"
                                        />
                                        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#E5E5E5] dark:border-[#2d3542] px-3 pt-3">
                                            <p className="text-xs leading-6 text-[#666666] dark:text-[#bcc5d3]">支持多轮续聊、历史保存和知识库引用展示。</p>
                                            <div className="flex items-center gap-2">
                                                <button
                                                    type="button"
                                                    onClick={() => void createConversation().catch((e) => setError(e instanceof Error ? e.message : '创建会话失败。'))}
                                                    className="inline-flex items-center gap-2 rounded-xl border border-[#E5E5E5] dark:border-[#2d3542] bg-white dark:bg-[#181c24] px-3 py-2 text-sm font-medium text-[#111111] dark:text-[#f4f7fb] transition hover:bg-[#F8F6F0] dark:hover:bg-[#2d3542]"
                                                >
                                                    <MessageSquarePlus className="h-4 w-4" />
                                                    新会话
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => void sendMessage()}
                                                    disabled={!input.trim() || sending}
                                                    className="inline-flex items-center gap-2 rounded-xl bg-[#111111] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#222222] disabled:cursor-not-allowed disabled:bg-[#B6B1A4]"
                                                >
                                                    {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                                                    发送
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </section>
                    </section>
                </div>
            </main>
        </div>
    )
}

'use client'

import { useEffect, useRef, useState } from 'react'
import { Bot, Loader2, MessageCircle, Send, X } from 'lucide-react'
import { usePathname } from 'next/navigation'
import { getBackendBaseUrl } from '@/lib/backend'
import MarkdownMessage from '@/components/MarkdownMessage'

const BACKEND_API_BASE = getBackendBaseUrl()
const ASSISTANT_TASK_POLL_INTERVAL_MS = 1200
const ASSISTANT_TASK_POLL_MAX_ATTEMPTS = 60

type ChatMessage = {
    id: string
    role: 'assistant' | 'user'
    content: string
}

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

export default function AssistantFloatingChat() {
    const pathname = usePathname() || ''
    const isAssistantPage = pathname.startsWith('/assistant')
    const [open, setOpen] = useState(false)
    const [userId, setUserId] = useState('default')
    const [conversationId, setConversationId] = useState('')
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [input, setInput] = useState('')
    const [sending, setSending] = useState(false)
    const [error, setError] = useState('')
    const listBottomRef = useRef<HTMLDivElement | null>(null)
    const textareaRef = useRef<HTMLTextAreaElement | null>(null)

    const loadAuth = async () => {
        const response = await fetch('/api/auth/me', { cache: 'no-store' })
        const data = await response.json().catch(() => ({}))
        const nextUserId = String(data?.user?.email || 'default').trim().toLowerCase() || 'default'
        setUserId(nextUserId)
        return nextUserId
    }

    const createConversation = async (currentUserId: string) => {
        const response = await fetch(`${BACKEND_API_BASE}/api/assistant/conversations`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: currentUserId }),
        })
        const data = await response.json().catch(() => ({}))
        if (!response.ok || !data?.success || !data?.conversation?.conversation_id) {
            throw new Error(data?.error || '创建会话失败。')
        }
        const nextConversationId = String(data.conversation.conversation_id)
        setConversationId(nextConversationId)
        return nextConversationId
    }

    const ensureConversation = async () => {
        const currentUserId = userId || (await loadAuth())
        if (conversationId) {
            return { currentUserId, currentConversationId: conversationId }
        }
        const currentConversationId = await createConversation(currentUserId)
        return { currentUserId, currentConversationId }
    }

    const patchPendingMessageContent = (pendingMessageId: string, content: string) => {
        setMessages((prev) =>
            prev.map((item) =>
                item.id === pendingMessageId
                    ? { ...item, content }
                    : item
            )
        )
    }

    const streamAssistantTask = (
        taskId: string,
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
            void pollAssistantTask(taskId, currentUserId, pendingMessageId)
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
                const failureMessage = String(task.error?.message || '分析失败，请稍后重试。')
                patchPendingMessageContent(pendingMessageId, `抱歉，这次分析失败：${failureMessage}`)
                setError(failureMessage)
                closeStream()
                return
            }

            if (status === 'completed') {
                finished = true
                const assistantPayload =
                    payload.assistant_message && typeof payload.assistant_message === 'object'
                        ? (payload.assistant_message as Record<string, unknown>)
                        : {}
                const assistantContent = String(assistantPayload.content || streamedText || '').trim()
                if (assistantContent) {
                    const assistantId = String(assistantPayload.message_id || `assistant_${Date.now()}`)
                    setMessages((prev) =>
                        prev.map((item) =>
                            item.id === pendingMessageId
                                ? { id: assistantId, role: 'assistant', content: assistantContent }
                                : item
                        )
                    )
                }
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
                            item.id === pendingMessageId
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
                            item.id === pendingMessageId
                                ? { ...item, content: `抱歉，这次分析失败：${reason}` }
                                : item
                        )
                    )
                    setError(reason)
                    return
                }
                if (status === 'completed') {
                    const assistantContent = String(data?.assistant_message?.content || task?.stream_text || '').trim()
                    if (assistantContent) {
                        setMessages((prev) =>
                            prev.map((item) =>
                                item.id === pendingMessageId
                                    ? { id: data?.assistant_message?.message_id || `assistant_${Date.now()}`, role: 'assistant', content: assistantContent }
                                    : item
                            )
                        )
                    }
                    return
                }
            } catch {
                // ignore transient polling errors
            }
        }

        setMessages((prev) =>
            prev.map((item) =>
                item.id === pendingMessageId
                    ? { ...item, content: '分析超时，建议稍后重试。' }
                    : item
            )
        )
        setError('AI助手处理超时，请稍后重试。')
    }

    const sendMessage = async () => {
        const content = input.trim()
        if (!content || sending) return

        setSending(true)
        setError('')

        const optimisticId = `local_${Date.now()}`
        setMessages((prev) => [...prev, { id: optimisticId, role: 'user', content }])
        setInput('')

        try {
            const { currentUserId, currentConversationId } = await ensureConversation()
            const response = await fetch(
                `${BACKEND_API_BASE}/api/assistant/conversations/${encodeURIComponent(currentConversationId)}/messages`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: currentUserId,
                        message: content,
                        temperature: 0.25,
                    }),
                }
            )
            const data = await response.json().catch(() => ({}))
            if (!response.ok || !data?.success) {
                throw new Error(data?.message || data?.error || '发送失败，请稍后重试。')
            }

            const isAsync = Boolean(data?.async)
            const taskId = String(data?.task?.task_id || '').trim()
            if (isAsync && taskId) {
                const pendingMessageId = `pending_${taskId}`
                const placeholderContent = String(data?.placeholder?.content || '已接收，正在分析你的问题...')
                setMessages((prev) => [...prev, { id: pendingMessageId, role: 'assistant', content: placeholderContent }])
                const streamStarted = streamAssistantTask(taskId, currentUserId, pendingMessageId)
                if (!streamStarted) {
                    void pollAssistantTask(taskId, currentUserId, pendingMessageId)
                }
            } else {
                const assistantContent = String(data?.assistant_message?.content || '').trim()
                if (assistantContent) {
                    setMessages((prev) => [...prev, { id: `assistant_${Date.now()}`, role: 'assistant', content: assistantContent }])
                }
            }
        } catch (sendError) {
            setError(sendError instanceof Error ? sendError.message : '发送失败，请稍后重试。')
            setMessages((prev) => prev.filter((item) => item.id !== optimisticId))
        } finally {
            setSending(false)
        }
    }

    const adjustTextareaHeight = () => {
        const textarea = textareaRef.current
        if (!textarea) return
        textarea.style.height = 'auto'
        textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`
    }

    useEffect(() => {
        if (isAssistantPage) return
        void loadAuth().catch(() => setUserId('default'))
    }, [isAssistantPage])

    useEffect(() => {
        listBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, sending, open])

    useEffect(() => {
        adjustTextareaHeight()
    }, [input])

    if (isAssistantPage) {
        return null
    }

    return (
        <>
            {open ? (
                <section className="fixed bottom-20 right-4 z-50 flex h-[600px] max-h-[80vh] w-[min(400px,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-[#0f0f0f]">
                    {/* Header */}
                    <header className="flex shrink-0 items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-800">
                        <div className="flex items-center gap-2.5">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-emerald-400 to-teal-600">
                                <Bot className="h-4 w-4 text-white" />
                            </div>
                            <div>
                                <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">AI 助手</p>
                                <p className="text-[11px] text-gray-400 dark:text-gray-500">随时为你解答</p>
                            </div>
                        </div>
                        <button
                            type="button"
                            onClick={() => setOpen(false)}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 transition hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-300"
                            aria-label="关闭"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </header>

                    {/* Messages */}
                    <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4">
                        {messages.length === 0 ? (
                            <div className="flex h-full flex-col items-center justify-center text-center">
                                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-emerald-400 to-teal-600">
                                    <Bot className="h-6 w-6 text-white" />
                                </div>
                                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">有什么可以帮你的？</p>
                                <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">输入问题即可开始对话</p>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {messages.map((message) => (
                                    <div key={message.id} className={`flex gap-2.5 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                        {message.role === 'assistant' ? (
                                            <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-emerald-400 to-teal-600">
                                                <Bot className="h-3.5 w-3.5 text-white" />
                                            </div>
                                        ) : null}

                                        <div className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-6 ${
                                            message.role === 'assistant'
                                                ? 'bg-gray-100 text-gray-900 dark:bg-[#1e1e1e] dark:text-gray-100'
                                                : 'bg-gray-900 text-white dark:bg-gray-700'
                                        }`}>
                                            {message.role === 'assistant' ? (
                                                <MarkdownMessage content={message.content} className="text-inherit" />
                                            ) : (
                                                <div className="whitespace-pre-wrap">{message.content}</div>
                                            )}
                                        </div>
                                    </div>
                                ))}

                                {sending ? (
                                    <div className="flex gap-2.5">
                                        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-emerald-400 to-teal-600">
                                            <Bot className="h-3.5 w-3.5 text-white" />
                                        </div>
                                        <div className="inline-flex items-center gap-1.5 rounded-2xl bg-gray-100 px-3.5 py-2.5 dark:bg-[#1e1e1e]">
                                            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.3s] dark:bg-gray-500" />
                                            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.15s] dark:bg-gray-500" />
                                            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 dark:bg-gray-500" />
                                        </div>
                                    </div>
                                ) : null}
                                <div ref={listBottomRef} />
                            </div>
                        )}
                    </div>

                    {/* Input */}
                    <div className="shrink-0 border-t border-gray-200 bg-white px-3 py-3 dark:border-gray-800 dark:bg-[#0f0f0f]">
                        {error ? (
                            <p className="mb-2 rounded-lg bg-red-50 px-2.5 py-1.5 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400">{error}</p>
                        ) : null}
                        <div className="flex items-end gap-2 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 focus-within:border-gray-400 dark:border-gray-700 dark:bg-[#1a1a1a] dark:focus-within:border-gray-500">
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
                                placeholder="输入问题..."
                                className="max-h-[120px] min-h-[20px] flex-1 resize-none bg-transparent text-sm leading-5 text-gray-900 outline-none placeholder:text-gray-400 dark:text-gray-100 dark:placeholder:text-gray-500"
                            />
                            <button
                                type="button"
                                onClick={() => void sendMessage()}
                                disabled={!input.trim() || sending}
                                className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gray-900 text-white transition hover:bg-gray-700 disabled:cursor-not-allowed disabled:bg-gray-300 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-200 dark:disabled:bg-gray-700"
                                aria-label="发送"
                            >
                                {sending ? (
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                    <Send className="h-3.5 w-3.5" />
                                )}
                            </button>
                        </div>
                    </div>
                </section>
            ) : null}

            {/* Toggle button */}
            <button
                type="button"
                onClick={() => setOpen((prev) => !prev)}
                className="fixed bottom-6 right-4 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-emerald-400 to-teal-600 text-white shadow-lg shadow-emerald-500/25 transition hover:scale-105 hover:shadow-xl hover:shadow-emerald-500/30"
                aria-label="打开 AI 助手"
            >
                <MessageCircle className="h-6 w-6" />
            </button>
        </>
    )
}

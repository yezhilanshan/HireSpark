'use client'

import { useEffect, useRef, useState } from 'react'
import { Bot, Loader2, Send, Sparkles, X } from 'lucide-react'
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

    const sendMessageLegacy = async () => {
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
                throw new Error(data?.message || data?.error || '发送失败。')
            }

            const assistantContent = String(data?.assistant_message?.content || '').trim()
            if (assistantContent) {
                setMessages((prev) => [...prev, { id: `assistant_${Date.now()}`, role: 'assistant', content: assistantContent }])
            }
        } catch (sendError) {
            setError(sendError instanceof Error ? sendError.message : '发送失败。')
            setMessages((prev) => prev.filter((item) => item.id !== optimisticId))
        } finally {
            setSending(false)
        }
    }

    void sendMessageLegacy

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

    useEffect(() => {
        if (isAssistantPage) return
        void loadAuth().catch(() => setUserId('default'))
    }, [isAssistantPage])

    useEffect(() => {
        listBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, sending, open])

    if (isAssistantPage) {
        return null
    }

    return (
        <>
            {open ? (
                <section className="fixed bottom-20 right-4 z-50 flex h-[760px] max-h-[86vh] w-[min(380px,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border border-[#D8E6DE] bg-white shadow-2xl">
                    <header className="flex items-center justify-between border-b border-[#EAE7DD] bg-[#F6FBF8] px-4 py-3">
                        <div className="flex items-center gap-2">
                            <span className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-emerald-200 bg-emerald-50 text-emerald-700">
                                <Bot className="h-4 w-4" />
                            </span>
                            <div>
                                <p className="text-sm font-semibold text-[#111111]">AI 小助手</p>
                            </div>
                        </div>
                        <button
                            type="button"
                            onClick={() => setOpen(false)}
                            className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-[#E5E5E5] text-[#666666] transition hover:bg-white hover:text-[#111111]"
                            aria-label="关闭小助手"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </header>

                    <div className="flex-1 min-h-0 space-y-3 overflow-y-auto bg-[#FCFCFA] px-4 py-4">
                        {messages.length === 0 ? (
                            <div className="rounded-xl border border-dashed border-[#D8D4CA] bg-white px-4 py-3 text-sm leading-6 text-[#666666]">
                                你可以随时提问，使用 PanelMind 中的问题也可以直接提问哦！
                            </div>
                        ) : (
                            messages.map((message) => (
                                <div key={message.id} className={`flex ${message.role === 'assistant' ? 'justify-start' : 'justify-end'}`}>
                                    <div
                                        className={`max-w-[88%] rounded-2xl px-3 py-2 text-sm leading-6 ${message.role === 'assistant'
                                            ? 'border border-[#E5E5E5] bg-white text-[#1A1A1A]'
                                            : 'bg-[#111111] text-white'
                                            }`}
                                    >
                                        {message.role === 'assistant' ? (
                                            <MarkdownMessage content={message.content} className="text-inherit" />
                                        ) : (
                                            <div className="whitespace-pre-wrap">{message.content}</div>
                                        )}
                                    </div>
                                </div>
                            ))
                        )}

                        {sending ? (
                            <div className="flex items-center gap-2 text-xs text-[#666666]">
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                助手正在思考...
                            </div>
                        ) : null}
                        <div ref={listBottomRef} />
                    </div>

                    <div className="border-t border-[#EAE7DD] bg-white p-3">
                        {error ? <p className="mb-2 text-xs text-red-600">{error}</p> : null}
                        <div className="flex items-center gap-2">
                            <textarea
                                value={input}
                                onChange={(event) => setInput(event.target.value)}
                                onKeyDown={(event) => {
                                    if (event.key === 'Enter' && !event.shiftKey) {
                                        event.preventDefault()
                                        void sendMessage()
                                    }
                                }}
                                rows={1}
                                placeholder="输入问题，回车发送"
                                className="h-[48px] min-h-[48px] max-h-[48px] flex-1 resize-none rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] px-3 py-2 text-sm text-[#111111] outline-none transition focus:border-[#111111]"
                            />
                            <button
                                type="button"
                                onClick={() => void sendMessage()}
                                disabled={!input.trim() || sending}
                                className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[#111111] text-white transition hover:bg-[#222222] disabled:cursor-not-allowed disabled:bg-[#B6B1A4]"
                                aria-label="发送消息"
                            >
                                <Send className="h-4 w-4" />
                            </button>
                        </div>
                    </div>
                </section>
            ) : null}

            <button
                type="button"
                onClick={() => setOpen((prev) => !prev)}
                className="fixed bottom-6 right-4 z-50 inline-flex items-center gap-2 rounded-xl border border-emerald-300/80 bg-white/90 px-4 py-2 text-sm font-semibold text-emerald-800 shadow-xl backdrop-blur transition hover:-translate-y-0.5 hover:bg-white"
                aria-label="打开 AI 小助手"
            >
                <Sparkles className="h-4 w-4" />
                AI 助手
            </button>
        </>
    )
}

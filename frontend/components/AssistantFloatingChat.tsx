'use client'

import { useMemo, useState } from 'react'
import { Bot, Loader2, Send, Sparkles, X } from 'lucide-react'
import { getBackendBaseUrl } from '@/lib/backend'

type AssistantRole = 'assistant' | 'user'

type AssistantMessage = {
    id: string
    role: AssistantRole
    content: string
}

type AssistantRequestError = Error & {
    status?: number
    code?: string
}

const BACKEND_API_BASE = getBackendBaseUrl()

const makeMessage = (role: AssistantRole, content: string): AssistantMessage => ({
    id: `${role}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    role,
    content,
})

export default function AssistantFloatingChat() {
    const [open, setOpen] = useState(false)
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const [messages, setMessages] = useState<AssistantMessage[]>([
        makeMessage('assistant', '你好，我是你的求职助理。你可以随时问我简历、项目表达、技术面试准备相关问题。'),
    ])
    const [errorText, setErrorText] = useState('')

    const canSend = useMemo(
        () => Boolean(input.trim()) && !loading,
        [input, loading]
    )

    const handleSend = async () => {
        const content = input.trim()
        if (!content || loading) {
            return
        }

        const userMessage = makeMessage('user', content)
        const nextMessages = [...messages, userMessage]
        setMessages(nextMessages)
        setInput('')
        setLoading(true)
        setErrorText('')

        try {
            const contextMessages = messages
                .slice(-6)
                .map((item) => ({
                    role: item.role,
                    content: item.content.slice(0, 1200),
                }))

            const requestOnce = async () => {
                const response = await fetch(`${BACKEND_API_BASE}/api/assistant/chat`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        message: content,
                        messages: contextMessages,
                        max_tokens: 384,
                        temperature: 0.25,
                    }),
                })
                const data = await response.json().catch(() => ({}))
                if (!response.ok || !data?.success) {
                    const detail = String(data?.error || data?.message || `HTTP ${response.status}`)
                    const err = new Error(detail) as AssistantRequestError
                    err.status = response.status
                    err.code = String(data?.error || '')
                    throw err
                }

                const reply = String(data?.reply || '').trim()
                if (!reply) {
                    const err = new Error('assistant empty reply') as AssistantRequestError
                    err.code = 'EMPTY_REPLY'
                    throw err
                }
                return reply
            }

            let reply = ''
            try {
                reply = await requestOnce()
            } catch (firstError) {
                const error = firstError as AssistantRequestError
                const isRetriable = Boolean(
                    (typeof error.status === 'number' && error.status >= 500) ||
                    error.code === 'EMPTY_REPLY' ||
                    error.code === 'OPENROUTER_EMPTY_CHOICES'
                )
                if (!isRetriable) {
                    throw firstError
                }
                await new Promise((resolve) => setTimeout(resolve, 350))
                reply = await requestOnce()
            }

            setMessages((prev) => [...prev, makeMessage('assistant', reply)])
        } catch (error) {
            const message = error instanceof Error ? error.message : 'assistant request failed'
            setErrorText(message)
            setMessages((prev) => [
                ...prev,
                makeMessage('assistant', '当前助理服务暂时不可用，请稍后重试。'),
            ])
        } finally {
            setLoading(false)
        }
    }

    return (
        <>
            <button
                type="button"
                onClick={() => setOpen((prev) => !prev)}
                className="fixed bottom-6 right-4 z-50 inline-flex items-center gap-2 rounded-xl border border-emerald-300/80 bg-white/90 px-4 py-2 text-sm font-semibold text-emerald-800 shadow-xl backdrop-blur transition hover:-translate-y-0.5 hover:bg-white dark:border-emerald-700 dark:bg-slate-900/90 dark:text-emerald-200 dark:hover:bg-slate-900"
                aria-label={open ? '关闭 AI 助理' : '打开 AI 助理'}
            >
                {open ? <X className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
                AI 助理
            </button>

            {open ? (
                <section className="fixed bottom-20 right-4 z-50 flex h-[68vh] w-[min(94vw,420px)] flex-col overflow-hidden rounded-2xl border border-[#E5E5E5] bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900">
                    <header className="flex items-center justify-between border-b border-[#E5E5E5] px-4 py-3 dark:border-slate-700">
                        <div className="flex items-center gap-2">
                            <Bot className="h-4 w-4 text-emerald-600 dark:text-emerald-300" />
                            <span className="text-sm font-semibold text-[#111111] dark:text-slate-100">求职 AI 助理</span>
                        </div>
                        <button
                            type="button"
                            onClick={() => setOpen(false)}
                            className="rounded-md p-1 text-[#666666] hover:bg-[#F4F4F4] hover:text-[#111111] dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                            aria-label="关闭面板"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </header>

                    <div className="flex-1 space-y-3 overflow-y-auto bg-[#FAFAF8] p-3 dark:bg-slate-950">
                        {messages.map((item) => (
                            <article
                                key={item.id}
                                className={`rounded-xl px-3 py-2 text-sm leading-6 ${
                                    item.role === 'assistant'
                                        ? 'mr-8 bg-white text-[#1A1A1A] shadow-sm dark:bg-slate-900 dark:text-slate-100'
                                        : 'ml-8 bg-emerald-600 text-white shadow-sm'
                                }`}
                            >
                                {item.content}
                            </article>
                        ))}
                        {loading ? (
                            <div className="flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-sm text-[#666666] shadow-sm dark:bg-slate-900 dark:text-slate-300">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                正在思考...
                            </div>
                        ) : null}
                    </div>

                    <footer className="border-t border-[#E5E5E5] p-3 dark:border-slate-700">
                        {errorText ? (
                            <p className="mb-2 text-xs text-red-600 dark:text-red-400">{errorText}</p>
                        ) : null}
                        <div className="flex items-end gap-2">
                            <textarea
                                value={input}
                                onChange={(event) => setInput(event.target.value)}
                                onKeyDown={(event) => {
                                    if (event.key === 'Enter' && !event.shiftKey) {
                                        event.preventDefault()
                                        handleSend()
                                    }
                                }}
                                placeholder="输入你的问题，回车发送..."
                                rows={2}
                                className="min-h-[44px] flex-1 resize-none rounded-lg border border-[#DADADA] bg-white px-3 py-2 text-sm text-[#111111] outline-none transition focus:border-emerald-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                            />
                            <button
                                type="button"
                                onClick={handleSend}
                                disabled={!canSend}
                                className="inline-flex h-11 items-center justify-center rounded-lg bg-emerald-600 px-3 text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-emerald-300"
                                aria-label="发送问题"
                            >
                                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                            </button>
                        </div>
                    </footer>
                </section>
            ) : null}
        </>
    )
}

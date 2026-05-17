'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

type MarkdownMessageProps = {
    content: string
    className?: string
}

function sanitizeAssistantMarkdown(raw: string): string {
    if (!raw) return ''
    return raw
        .replace(/<br\s*\/?>/gi, '；')
        .replace(/[（(]\s*(?:见|参见|详见)\s*[^()（）\n]{0,140}[)）]/g, '')
        .replace(/(?:见|参见|详见)\s*knowledge\/[^\s，。；;、)]{1,80}/gi, '')
        .replace(/\s*；\s*；+/g, '；')
        .replace(/\n{3,}/g, '\n\n')
        .trim()
}

export default function MarkdownMessage({ content, className }: MarkdownMessageProps) {
    const safeContent = sanitizeAssistantMarkdown(content)

    return (
        <div className={className}>
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    p: ({ children }) => <p className="mb-2 leading-7 last:mb-0">{children}</p>,
                    ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-6 last:mb-0">{children}</ol>,
                    ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-6 last:mb-0">{children}</ul>,
                    li: ({ children }) => <li className="leading-7">{children}</li>,
                    h1: ({ children }) => <h1 className="mb-2 text-lg font-semibold last:mb-0">{children}</h1>,
                    h2: ({ children }) => <h2 className="mb-2 text-base font-semibold last:mb-0">{children}</h2>,
                    h3: ({ children }) => <h3 className="mb-2 text-sm font-semibold last:mb-0">{children}</h3>,
                    code: ({ children }) => (
                        <code className="rounded bg-black/5 px-1.5 py-0.5 text-[0.9em] leading-6 dark:bg-white/10">{children}</code>
                    ),
                    pre: ({ children }) => (
                        <pre className="mb-2 overflow-x-auto rounded-xl border border-black/10 bg-black/5 p-3 text-xs leading-6 last:mb-0 dark:border-white/10 dark:bg-white/5">
                            {children}
                        </pre>
                    ),
                    table: ({ children }) => (
                        <div className="mb-2 overflow-x-auto rounded-xl border border-black/10 last:mb-0 dark:border-white/10">
                            <table className="w-full border-collapse text-left text-xs">{children}</table>
                        </div>
                    ),
                    thead: ({ children }) => <thead className="bg-black/5 dark:bg-white/5">{children}</thead>,
                    th: ({ children }) => <th className="border-b border-black/10 px-3 py-2 font-semibold dark:border-white/10">{children}</th>,
                    td: ({ children }) => <td className="border-b border-black/5 px-3 py-2 align-top dark:border-white/5">{children}</td>,
                    a: ({ children, href }) => (
                        <a
                            href={href}
                            target="_blank"
                            rel="noreferrer"
                            className="text-emerald-700 underline underline-offset-2 dark:text-emerald-400"
                        >
                            {children}
                        </a>
                    ),
                    blockquote: ({ children }) => (
                        <blockquote className="mb-2 border-l-2 border-gray-300 pl-4 text-gray-600 last:mb-0 dark:border-gray-600 dark:text-gray-400">
                            {children}
                        </blockquote>
                    ),
                    hr: () => <hr className="my-4 border-gray-200 dark:border-gray-700" />,
                }}
            >
                {safeContent}
            </ReactMarkdown>
        </div>
    )
}

'use client'

import Link from 'next/link'
import { UserCircle2 } from 'lucide-react'

export default function MyEntry() {
    return (
        <Link
            href="/me"
            className="fixed right-40 top-4 z-50 inline-flex items-center gap-2 rounded-xl border border-cyan-300/80 bg-white/85 px-4 py-2 text-sm font-semibold text-cyan-800 shadow-xl backdrop-blur transition hover:-translate-y-0.5 hover:bg-white dark:border-cyan-700 dark:bg-slate-900/85 dark:text-cyan-200 dark:hover:bg-slate-900"
            aria-label="进入我的信息页面"
        >
            <UserCircle2 className="h-5 w-5" />
            我的空间
        </Link>
    )
}

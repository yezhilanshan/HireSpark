import { cn } from '@/lib/utils'
import React from 'react'

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
    return (
        <div className={cn('motion-hover-lift rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-[0_2px_8px_rgba(0,0,0,0.02)] dark:shadow-[0_2px_8px_rgba(0,0,0,0.3)]', className)} {...props} />
    )
}

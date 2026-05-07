export default function RootLoading() {
    return (
        <div className="flex h-screen w-full items-center justify-center">
            <div className="flex flex-col items-center gap-4">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--border)] border-t-[var(--ink)]" />
                <p className="text-sm text-[var(--ink-muted)]">加载中...</p>
            </div>
        </div>
    )
}

export default function QuestionsLoading() {
    return (
        <div className="flex-1 min-h-0 overflow-y-auto p-8 lg:p-12">
            <div className="max-w-6xl mx-auto space-y-8 animate-pulse">
                <div className="flex items-center justify-between">
                    <div>
                        <div className="h-8 w-32 rounded-lg bg-[var(--accent)]" />
                        <div className="mt-2 h-4 w-48 rounded bg-[var(--accent)]" />
                    </div>
                    <div className="h-10 w-40 rounded-lg bg-[var(--accent)]" />
                </div>
                <div className="h-10 w-full rounded-lg bg-[var(--accent)]" />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {[...Array(6)].map((_, i) => (
                        <div key={i} className="h-40 rounded-2xl bg-[var(--accent)]" />
                    ))}
                </div>
            </div>
        </div>
    )
}

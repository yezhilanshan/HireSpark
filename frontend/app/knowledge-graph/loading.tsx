export default function KnowledgeGraphLoading() {
    return (
        <div className="flex-1 min-h-0 overflow-y-auto p-8 lg:p-12">
            <div className="max-w-6xl mx-auto space-y-8 animate-pulse">
                <div className="flex items-center justify-between">
                    <div className="h-8 w-48 rounded-lg bg-[var(--accent)]" />
                    <div className="h-9 w-32 rounded-lg bg-[var(--accent)]" />
                </div>
                <div className="h-[500px] rounded-2xl bg-[var(--accent)]" />
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                    <div className="h-80 rounded-2xl bg-[var(--accent)]" />
                    <div className="h-80 rounded-2xl bg-[var(--accent)]" />
                </div>
            </div>
        </div>
    )
}

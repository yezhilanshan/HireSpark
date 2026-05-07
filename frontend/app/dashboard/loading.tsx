export default function DashboardLoading() {
    return (
        <div className="flex-1 min-h-0 overflow-y-auto p-8 lg:p-12">
            <div className="max-w-6xl mx-auto space-y-8 animate-pulse">
                <div className="h-8 w-48 rounded-lg bg-[var(--accent)]" />
                <div className="h-4 w-96 rounded bg-[var(--accent)]" />
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {[...Array(4)].map((_, i) => (
                        <div key={i} className="h-24 rounded-2xl bg-[var(--accent)]" />
                    ))}
                </div>
                <div className="h-64 rounded-2xl bg-[var(--accent)]" />
            </div>
        </div>
    )
}

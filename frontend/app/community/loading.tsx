export default function CommunityLoading() {
    return (
        <div className="flex-1 min-h-0 overflow-y-auto p-8 lg:p-12">
            <div className="max-w-5xl mx-auto space-y-8 animate-pulse">
                <div className="flex items-center justify-between">
                    <div>
                        <div className="h-8 w-32 rounded-lg bg-[var(--accent)]" />
                        <div className="mt-2 h-4 w-64 rounded bg-[var(--accent)]" />
                    </div>
                    <div className="h-10 w-32 rounded-lg bg-[var(--accent)]" />
                </div>
                <div className="flex gap-2">
                    <div className="h-10 w-24 rounded-full bg-[var(--accent)]" />
                    <div className="h-10 w-24 rounded-full bg-[var(--accent)]" />
                </div>
                <div className="space-y-4">
                    {[...Array(5)].map((_, i) => (
                        <div key={i} className="h-28 rounded-2xl bg-[var(--accent)]" />
                    ))}
                </div>
            </div>
        </div>
    )
}

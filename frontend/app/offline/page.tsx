export default function OfflinePage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--background)] p-6">
      <div className="text-center max-w-sm">
        <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-slate-900 to-blue-700 flex items-center justify-center">
          <svg width="40" height="40" viewBox="0 0 64 64" fill="none">
            <path d="M18 46V18h8l6 9 6-9h8v28h-8V31l-6 9-6-9v15z" fill="#f8fafc" />
            <circle cx="48" cy="18" r="6" fill="url(#grad)" />
            <defs>
              <linearGradient id="grad" x1="0%" x2="100%" y1="0%" y2="100%">
                <stop offset="0%" stopColor="#38bdf8" />
                <stop offset="100%" stopColor="#f59e0b" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        <h1 className="text-xl font-semibold text-[var(--ink)] mb-2">网络连接已断开</h1>
        <p className="text-sm text-[var(--ink-secondary)] mb-8 leading-relaxed">
          您当前处于离线状态。请检查网络连接后重试。恢复网络后，所有功能将恢复正常使用。
        </p>

        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-[var(--accent)] text-white font-medium text-sm hover:opacity-90 transition-opacity"
        >
          重新连接
        </button>
      </div>
    </div>
  )
}

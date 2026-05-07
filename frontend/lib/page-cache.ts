type CacheEnvelope<T> = {
    cachedAt: number
    data: T
}

const memoryCache = new Map<string, CacheEnvelope<unknown>>()

function isClient(): boolean {
    return typeof window !== 'undefined'
}

function normalizeCachedAt(value: unknown): number {
    const numeric = Number(value)
    if (!Number.isFinite(numeric) || numeric <= 0) return 0
    return numeric
}

export function buildPageCacheKey(prefix: string, scope?: string): string {
    const normalizedPrefix = String(prefix || '').trim() || 'page-cache'
    const normalizedScope = String(scope || '').trim()
    return normalizedScope ? `${normalizedPrefix}:${normalizedScope}` : normalizedPrefix
}

export function readPageCache<T>(key: string, ttlMs: number): T | null {
    const normalizedKey = String(key || '').trim()
    if (!normalizedKey || !isClient()) return null

    const now = Date.now()
    const safeTtlMs = Math.max(0, Number(ttlMs) || 0)

    const memoryEntry = memoryCache.get(normalizedKey)
    if (memoryEntry) {
        const age = now - normalizeCachedAt(memoryEntry.cachedAt)
        if (safeTtlMs <= 0 || age <= safeTtlMs) {
            return memoryEntry.data as T
        }
        memoryCache.delete(normalizedKey)
    }

    try {
        const raw = window.sessionStorage.getItem(normalizedKey)
        if (!raw) return null

        const parsed = JSON.parse(raw) as Partial<CacheEnvelope<T>>
        const cachedAt = normalizeCachedAt(parsed?.cachedAt)
        if (!cachedAt) {
            window.sessionStorage.removeItem(normalizedKey)
            return null
        }

        const age = now - cachedAt
        if (safeTtlMs > 0 && age > safeTtlMs) {
            window.sessionStorage.removeItem(normalizedKey)
            return null
        }

        const envelope: CacheEnvelope<T> = {
            cachedAt,
            data: (parsed?.data ?? null) as T,
        }

        memoryCache.set(normalizedKey, envelope as CacheEnvelope<unknown>)
        return envelope.data
    } catch {
        return null
    }
}

export function writePageCache<T>(key: string, data: T): void {
    const normalizedKey = String(key || '').trim()
    if (!normalizedKey || !isClient()) return

    const envelope: CacheEnvelope<T> = {
        cachedAt: Date.now(),
        data,
    }

    memoryCache.set(normalizedKey, envelope as CacheEnvelope<unknown>)
    try {
        window.sessionStorage.setItem(normalizedKey, JSON.stringify(envelope))
    } catch {
        // ignore storage failures
    }
}

export function removePageCache(key: string): void {
    const normalizedKey = String(key || '').trim()
    if (!normalizedKey) return

    memoryCache.delete(normalizedKey)
    if (!isClient()) return

    try {
        window.sessionStorage.removeItem(normalizedKey)
    } catch {
        // ignore storage failures
    }
}
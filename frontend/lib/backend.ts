const DEFAULT_BACKEND_PORT = '5000'
const DEFAULT_SERVER_BACKEND_HOST = '127.0.0.1'

const trimTrailingSlash = (url: string): string => url.replace(/\/+$/, '')

const firstNonEmpty = (...values: Array<string | undefined>): string | null => {
    for (const value of values) {
        const trimmed = value?.trim()
        if (trimmed) {
            return trimmed
        }
    }
    return null
}

export const getBackendBaseUrl = (): string => {
    const configured = firstNonEmpty(
        process.env.NEXT_PUBLIC_BACKEND_URL,
        process.env.NEXT_PUBLIC_API_URL,
    )

    if (configured) {
        return trimTrailingSlash(configured)
    }

    if (typeof window !== 'undefined') {
        const { protocol, hostname } = window.location
        return `${protocol}//${hostname}:${DEFAULT_BACKEND_PORT}`
    }

    return `http://${DEFAULT_SERVER_BACKEND_HOST}:${DEFAULT_BACKEND_PORT}`
}

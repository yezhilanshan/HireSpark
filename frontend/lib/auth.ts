export const AUTH_COOKIE_NAME = 'zhiyuexingchen_session'

export const DEFAULT_LOGIN_EMAIL = 'admin@zhiyuexingchen.cn'
export const DEFAULT_LOGIN_PASSWORD = '职跃星辰123'
export const DEFAULT_LOGIN_NAME = '职跃星辰 管理员'

const DEFAULT_SESSION_TTL_SECONDS = 60 * 60 * 24 * 7

export type AuthSession = {
    email: string
    name: string
    exp: number
}

const trimTrailingSlash = (value: string): string => value.replace(/\/+$/, '')

const firstNonEmpty = (...values: Array<string | undefined>): string | null => {
    for (const value of values) {
        const normalized = String(value || '').trim()
        if (normalized) return normalized
    }
    return null
}

export function getAuthBackendBaseUrl(): string {
    const configured = firstNonEmpty(
        process.env.BACKEND_ORIGIN,
        process.env.VERCEL_BACKEND_ORIGIN,
        process.env.NEXT_PUBLIC_API_URL,
        process.env.NEXT_PUBLIC_BACKEND_URL,
    )

    if (configured && /^https?:\/\//i.test(configured)) {
        return trimTrailingSlash(configured)
    }

    return 'http://127.0.0.1:5000'
}

export function shouldUseSecureCookies(): boolean {
    const explicit = String(process.env.AUTH_COOKIE_SECURE || '').trim().toLowerCase()
    if (explicit === 'true' || explicit === '1' || explicit === 'yes') return true
    if (explicit === 'false' || explicit === '0' || explicit === 'no') return false

    const publicSiteUrl = String(process.env.PUBLIC_SITE_URL || '').trim().toLowerCase()
    if (publicSiteUrl.startsWith('https://')) return true
    if (publicSiteUrl.startsWith('http://')) return false

    return process.env.NODE_ENV === 'production' && false
}

export function buildSessionCookieValue(
    email: string,
    name: string,
    ttlSeconds: number = DEFAULT_SESSION_TTL_SECONDS,
): string {
    const exp = Math.floor(Date.now() / 1000) + Math.max(300, Math.floor(ttlSeconds))
    return `${exp}|${encodeURIComponent(String(email || '').trim().toLowerCase())}|${encodeURIComponent(String(name || '').trim())}`
}

export function parseSessionCookieValue(value?: string | null): AuthSession | null {
    const raw = String(value || '').trim()
    if (!raw) return null
    const [expRaw, emailRaw, nameRaw] = raw.split('|')
    const exp = Number(expRaw)
    if (!Number.isFinite(exp) || exp <= 0) return null

    const email = decodeURIComponent(String(emailRaw || '')).trim().toLowerCase()
    const name = decodeURIComponent(String(nameRaw || '')).trim()
    if (!email || !name) return null

    return { email, name, exp }
}

export function isSessionValid(session: AuthSession | null | undefined): session is AuthSession {
    if (!session) return false
    return session.exp > Math.floor(Date.now() / 1000)
}

export function resolveSafeRedirect(nextValue?: string | null): string {
    const candidate = String(nextValue || '').trim()
    if (!candidate.startsWith('/')) return '/dashboard'
    if (candidate.startsWith('//')) return '/dashboard'
    if (candidate === '/') return '/dashboard'
    return candidate
}

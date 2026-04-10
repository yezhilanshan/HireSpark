export const AUTH_COOKIE_NAME = 'panelmind_session'

const DEFAULT_LOGIN_EMAIL = 'admin@panelmind.cn'
const DEFAULT_LOGIN_PASSWORD = 'PanelMind123'
const DEFAULT_LOGIN_NAME = 'PanelMind 管理员'
const DEFAULT_SESSION_TTL_SECONDS = 60 * 60 * 24 * 7

export type AuthSession = {
    email: string
    name: string
    exp: number
}

export function getConfiguredAuthUser() {
    return {
        email: String(process.env.AUTH_LOGIN_EMAIL || DEFAULT_LOGIN_EMAIL).trim().toLowerCase(),
        password: String(process.env.AUTH_LOGIN_PASSWORD || DEFAULT_LOGIN_PASSWORD),
        name: String(process.env.AUTH_LOGIN_NAME || DEFAULT_LOGIN_NAME).trim() || DEFAULT_LOGIN_NAME,
    }
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

export function buildSessionCookieValue(email: string, name: string, ttlSeconds: number = DEFAULT_SESSION_TTL_SECONDS): string {
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

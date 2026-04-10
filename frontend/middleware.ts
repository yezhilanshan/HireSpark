import { NextRequest, NextResponse } from 'next/server'

const AUTH_COOKIE_NAME = 'panelmind_session'

type AuthSession = {
    email: string
    name: string
    exp: number
}

function parseSessionCookieValue(value?: string | null): AuthSession | null {
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

function isSessionValid(session: AuthSession | null | undefined): session is AuthSession {
    if (!session) return false
    return session.exp > Math.floor(Date.now() / 1000)
}

function shouldUseSecureCookies(): boolean {
    const explicit = String(process.env.AUTH_COOKIE_SECURE || '').trim().toLowerCase()
    if (explicit === 'true' || explicit === '1' || explicit === 'yes') return true
    if (explicit === 'false' || explicit === '0' || explicit === 'no') return false

    const publicSiteUrl = String(process.env.PUBLIC_SITE_URL || '').trim().toLowerCase()
    if (publicSiteUrl.startsWith('https://')) return true
    if (publicSiteUrl.startsWith('http://')) return false

    return false
}

const PROTECTED_PREFIXES = [
    '/dashboard',
    '/history',
    '/insights',
    '/interview',
    '/interview-setup',
    '/liveness',
    '/me',
    '/replay',
    '/report',
    '/review',
    '/settings',
]

function isProtectedPath(pathname: string): boolean {
    return PROTECTED_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))
}

export function middleware(request: NextRequest) {
    const { pathname, search } = request.nextUrl
    const session = parseSessionCookieValue(request.cookies.get(AUTH_COOKIE_NAME)?.value)
    const authenticated = isSessionValid(session)

    if (pathname === '/') {
        const response = NextResponse.next()
        if (request.cookies.get(AUTH_COOKIE_NAME)?.value) {
            response.cookies.set({
                name: AUTH_COOKIE_NAME,
                value: '',
                httpOnly: true,
                sameSite: 'lax',
                secure: shouldUseSecureCookies(),
                path: '/',
                expires: new Date(0),
                maxAge: 0,
            })
        }
        return response
    }

    if (isProtectedPath(pathname) && !authenticated) {
        const loginUrl = new URL('/', request.url)
        loginUrl.searchParams.set('next', `${pathname}${search}`)
        return NextResponse.redirect(loginUrl)
    }

    return NextResponse.next()
}

export const config = {
    matcher: ['/((?!api/auth|_next/static|_next/image|favicon.ico|icon.svg).*)'],
}

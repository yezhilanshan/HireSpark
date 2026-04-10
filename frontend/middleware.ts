import { NextRequest, NextResponse } from 'next/server'

const AUTH_COOKIE_NAME = 'panelmind_session'

function parseSessionExpiry(value?: string | null): number | null {
    try {
        const raw = String(value || '').trim()
        if (!raw) return null
        const [expRaw] = raw.split('|')
        const exp = Number(expRaw)
        if (!Number.isFinite(exp) || exp <= 0) return null
        return exp
    } catch {
        return null
    }
}

function isSessionValid(expiry: number | null | undefined): boolean {
    if (!expiry) return false
    return expiry > Math.floor(Date.now() / 1000)
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
    try {
        const { pathname, search } = request.nextUrl
        const cookieValue = request.cookies.get(AUTH_COOKIE_NAME)?.value
        const authenticated = isSessionValid(parseSessionExpiry(cookieValue))

        if (pathname === '/') {
            const response = NextResponse.next()
            if (cookieValue) {
                response.cookies.delete(AUTH_COOKIE_NAME)
            }
            return response
        }

        if (isProtectedPath(pathname) && !authenticated) {
            const loginUrl = new URL('/', request.url)
            loginUrl.searchParams.set('next', `${pathname}${search}`)
            return NextResponse.redirect(loginUrl)
        }

        return NextResponse.next()
    } catch {
        return NextResponse.next()
    }
}

export const config = {
    matcher: ['/((?!api/auth|_next/static|_next/image|favicon.ico|icon.svg).*)'],
}

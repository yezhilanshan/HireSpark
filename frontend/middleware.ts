import { NextRequest, NextResponse } from 'next/server'
import { AUTH_COOKIE_NAME, isSessionValid, parseSessionCookieValue, resolveSafeRedirect, shouldUseSecureCookies } from '@/lib/auth'

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

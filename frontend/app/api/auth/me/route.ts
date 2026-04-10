import { NextRequest, NextResponse } from 'next/server'
import { AUTH_COOKIE_NAME, isSessionValid, parseSessionCookieValue } from '@/lib/auth'

export async function GET(request: NextRequest) {
    const session = parseSessionCookieValue(request.cookies.get(AUTH_COOKIE_NAME)?.value)

    if (!isSessionValid(session)) {
        return NextResponse.json(
            { success: false, authenticated: false, error: '未登录' },
            { status: 401 }
        )
    }

    return NextResponse.json({
        success: true,
        authenticated: true,
        user: {
            email: session.email,
            name: session.name,
        },
    })
}


import { NextRequest, NextResponse } from 'next/server'
import { AUTH_COOKIE_NAME, buildSessionCookieValue, getConfiguredAuthUser, shouldUseSecureCookies } from '@/lib/auth'

export async function POST(request: NextRequest) {
    try {
        const body = await request.json().catch(() => ({}))
        const email = String(body?.email || '').trim().toLowerCase()
        const password = String(body?.password || '')
        const authUser = getConfiguredAuthUser()

        if (!email || !password) {
            return NextResponse.json(
                { success: false, error: '请填写邮箱和密码。' },
                { status: 400 }
            )
        }

        if (email !== authUser.email || password !== authUser.password) {
            return NextResponse.json(
                { success: false, error: '邮箱或密码不正确。' },
                { status: 401 }
            )
        }

        const response = NextResponse.json({
            success: true,
            user: {
                email: authUser.email,
                name: authUser.name,
            },
        })

        response.cookies.set({
            name: AUTH_COOKIE_NAME,
            value: buildSessionCookieValue(authUser.email, authUser.name),
            httpOnly: true,
            sameSite: 'lax',
            secure: shouldUseSecureCookies(),
            path: '/',
        })

        return response
    } catch {
        return NextResponse.json(
            { success: false, error: '登录失败，请稍后重试。' },
            { status: 500 }
        )
    }
}

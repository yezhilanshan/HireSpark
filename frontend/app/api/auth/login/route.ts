import { NextRequest, NextResponse } from 'next/server'
import { AUTH_COOKIE_NAME, buildSessionCookieValue, getAuthBackendBaseUrl, shouldUseSecureCookies } from '@/lib/auth'

export async function POST(request: NextRequest) {
    try {
        const body = await request.json().catch(() => ({}))
        const email = String(body?.email || '').trim().toLowerCase()
        const password = String(body?.password || '')

        if (!email || !password) {
            return NextResponse.json(
                { success: false, error: '请输入完整的邮箱和密码。' },
                { status: 400 },
            )
        }

        const upstream = await fetch(`${getAuthBackendBaseUrl()}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
            cache: 'no-store',
        })

        const upstreamData = await upstream.json().catch(() => ({}))
        if (!upstream.ok || !upstreamData?.success) {
            return NextResponse.json(
                { success: false, error: upstreamData?.error || '登录失败，请稍后重试。' },
                { status: upstream.status || 401 },
            )
        }

        const userEmail = String(upstreamData?.user?.email || email).trim().toLowerCase()
        const userName = String(upstreamData?.user?.name || 'HireSpark 用户').trim() || 'HireSpark 用户'

        const response = NextResponse.json({
            success: true,
            user: {
                email: userEmail,
                name: userName,
            },
        })

        response.cookies.set({
            name: AUTH_COOKIE_NAME,
            value: buildSessionCookieValue(userEmail, userName),
            httpOnly: true,
            sameSite: 'lax',
            secure: shouldUseSecureCookies(),
            path: '/',
        })

        return response
    } catch {
        return NextResponse.json(
            { success: false, error: '登录失败，请稍后重试。' },
            { status: 500 },
        )
    }
}

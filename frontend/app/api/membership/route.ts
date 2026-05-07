import { NextRequest, NextResponse } from 'next/server'
import { AUTH_COOKIE_NAME, getAuthBackendBaseUrl, isSessionValid, parseSessionCookieValue } from '@/lib/auth'

function getSessionOrResponse(request: NextRequest) {
    const session = parseSessionCookieValue(request.cookies.get(AUTH_COOKIE_NAME)?.value)
    if (!isSessionValid(session)) {
        return NextResponse.json(
            { success: false, error: '请先登录后再查看会员信息。' },
            { status: 401 },
        )
    }
    return session
}

export async function GET(request: NextRequest) {
    const sessionOrResponse = getSessionOrResponse(request)
    if (sessionOrResponse instanceof NextResponse) return sessionOrResponse

    const session = sessionOrResponse
    try {
        const upstream = await fetch(
            `${getAuthBackendBaseUrl()}/api/membership/overview?user_email=${encodeURIComponent(session.email)}`,
            { cache: 'no-store' },
        )
        const data = await upstream.json().catch(() => ({}))
        return NextResponse.json(data, { status: upstream.status || 200 })
    } catch {
        return NextResponse.json(
            { success: false, error: '会员服务暂时不可用，请稍后重试。' },
            { status: 500 },
        )
    }
}

export async function POST(request: NextRequest) {
    const sessionOrResponse = getSessionOrResponse(request)
    if (sessionOrResponse instanceof NextResponse) return sessionOrResponse

    const session = sessionOrResponse
    try {
        const body = await request.json().catch(() => ({}))
        const upstream = await fetch(`${getAuthBackendBaseUrl()}/api/membership/orders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_email: session.email,
                membership_mode: body?.membership_mode,
                plan_id: body?.plan_id,
                team_size: body?.team_size,
            }),
            cache: 'no-store',
        })
        const data = await upstream.json().catch(() => ({}))
        return NextResponse.json(data, { status: upstream.status || 200 })
    } catch {
        return NextResponse.json(
            { success: false, error: '创建订单失败，请稍后重试。' },
            { status: 500 },
        )
    }
}

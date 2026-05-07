import { NextRequest, NextResponse } from 'next/server'
import { AUTH_COOKIE_NAME, getAuthBackendBaseUrl, isSessionValid, parseSessionCookieValue } from '@/lib/auth'

export async function POST(request: NextRequest) {
    const session = parseSessionCookieValue(request.cookies.get(AUTH_COOKIE_NAME)?.value)
    if (!isSessionValid(session)) {
        return NextResponse.json(
            { success: false, error: '请先登录后再支付开通会员。' },
            { status: 401 },
        )
    }

    try {
        const body = await request.json().catch(() => ({}))
        const orderId = String(body?.order_id || '').trim()
        if (!orderId) {
            return NextResponse.json(
                { success: false, error: '缺少订单号。' },
                { status: 400 },
            )
        }

        const upstream = await fetch(`${getAuthBackendBaseUrl()}/api/membership/orders/pay`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_email: session.email,
                order_id: orderId,
            }),
            cache: 'no-store',
        })
        const data = await upstream.json().catch(() => ({}))
        return NextResponse.json(data, { status: upstream.status || 200 })
    } catch {
        return NextResponse.json(
            { success: false, error: '支付开通失败，请稍后重试。' },
            { status: 500 },
        )
    }
}

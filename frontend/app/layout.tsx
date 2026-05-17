import type { Metadata, Viewport } from 'next'
import localFont from 'next/font/local'
import './globals.css'
import { ThemeProvider } from '@/components/ThemeProvider'
import ClientLayout from '@/components/ClientLayout'
import { PwaRegister } from '@/components/PwaRegister'

const sansFont = localFont({
    src: [{ path: './fonts/NotoSansSC-VF.ttf', weight: '100 900', style: 'normal' }],
    variable: '--font-sans',
    display: 'swap',
})
const serifFont = localFont({
    src: [{ path: './fonts/NotoSerifSC-VF.ttf', weight: '100 900', style: 'normal' }],
    variable: '--font-serif',
    display: 'swap',
})

export const viewport: Viewport = {
    width: 'device-width',
    initialScale: 1,
    maximumScale: 1,
    userScalable: false,
    themeColor: [
        { media: '(prefers-color-scheme: dark)', color: '#0f172a' },
        { media: '(prefers-color-scheme: light)', color: '#f8fafc' },
    ],
}

export const metadata: Metadata = {
    title: '职跃星辰',
    description: '岗位化 AI 模拟面试与能力提升平台',
    manifest: '/manifest.json',
    appleWebApp: {
        capable: true,
        statusBarStyle: 'black-translucent',
        title: '职跃星辰',
    },
    icons: {
        icon: '/icons/icon-192.png',
        shortcut: '/icons/icon-192.png',
        apple: '/icons/apple-touch-icon.png',
    },
    other: {
        'mobile-web-app-capable': 'yes',
    },
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html
            lang="zh-CN"
            className={`${sansFont.variable} ${serifFont.variable}`}
            suppressHydrationWarning
        >
            <body className="font-sans bg-[var(--background)] text-[var(--ink)] antialiased selection:bg-[var(--accent)] selection:text-[var(--ink)] transition-colors duration-300">
                <ThemeProvider>
                    {children}
                    <ClientLayout />
                    <PwaRegister />
                </ThemeProvider>
            </body>
        </html>
    )
}

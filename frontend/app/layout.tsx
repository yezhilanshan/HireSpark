import type { Metadata } from 'next'
import './globals.css'
import { ThemeProvider } from '@/components/ThemeProvider'
import GlobalFloatingActions from '@/components/GlobalFloatingActions'

export const metadata: Metadata = {
    title: '天枢智面',
    description: '岗位化 AI 模拟面试与能力提升平台',
    icons: {
        icon: '/icon.svg',
        shortcut: '/icon.svg',
        apple: '/icon.svg',
    },
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="zh-CN" suppressHydrationWarning>
            <body className="antialiased">
                <ThemeProvider>
                    <GlobalFloatingActions />
                    {children}
                </ThemeProvider>
            </body>
        </html>
    )
}

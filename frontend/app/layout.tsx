import type { Metadata, Viewport } from 'next'
import { Inter, Newsreader } from 'next/font/google'
import localFont from 'next/font/local'
import './globals.css'
import { ThemeProvider } from '@/components/ThemeProvider'
import ClientLayout from '@/components/ClientLayout'
import { PwaRegister } from '@/components/PwaRegister'

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' })
const newsreader = Newsreader({ subsets: ['latin'], variable: '--font-serif', style: ['normal', 'italic'] })
const sourceHanSans = localFont({
    src: [{ path: './fonts/NotoSansSC-VF.ttf', weight: '100 900', style: 'normal' }],
    variable: '--font-zh-sans',
    display: 'swap',
})
const sourceHanSerif = localFont({
    src: [{ path: './fonts/NotoSerifSC-VF.ttf', weight: '100 900', style: 'normal' }],
    variable: '--font-zh-serif',
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
    title: 'PanelMind',
    description: '岗位化 AI 模拟面试与能力提升平台',
    manifest: '/manifest.json',
    appleWebApp: {
        capable: true,
        statusBarStyle: 'black-translucent',
        title: 'PanelMind',
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
            className={`${inter.variable} ${newsreader.variable} ${sourceHanSans.variable} ${sourceHanSerif.variable}`}
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

import type { Metadata } from 'next'
import { Inter, Newsreader, Noto_Sans_SC, Noto_Serif_SC } from 'next/font/google'
import './globals.css'
import { CommandPalette } from '@/components/command-palette'
import { ThemeProvider } from '@/components/ThemeProvider'
import GlobalFloatingActions from '@/components/GlobalFloatingActions'

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' })
const newsreader = Newsreader({ subsets: ['latin'], variable: '--font-serif', style: ['normal', 'italic'] })
const sourceHanSans = Noto_Sans_SC({
    variable: '--font-zh-sans',
    weight: ['400', '500', '600', '700'],
    preload: false,
})
const sourceHanSerif = Noto_Serif_SC({
    variable: '--font-zh-serif',
    weight: ['400', '500', '600', '700'],
    preload: false,
})

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
        <html lang="zh-CN" className={`${inter.variable} ${newsreader.variable} ${sourceHanSans.variable} ${sourceHanSerif.variable}`} suppressHydrationWarning>
            <body className="font-sans bg-[#FAF9F6] text-[#1A1A1A] antialiased selection:bg-[#EBE9E0] selection:text-[#1A1A1A]">
                <ThemeProvider>
                    {children}
                    <GlobalFloatingActions />
                    <CommandPalette />
                </ThemeProvider>
            </body>
        </html>
    )
}

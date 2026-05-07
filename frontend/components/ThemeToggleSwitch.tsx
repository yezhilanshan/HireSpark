'use client'

import { Moon, Sun } from 'lucide-react'
import { useTheme } from './ThemeProvider'

export default function ThemeToggleSwitch() {
    const { resolvedTheme, setTheme } = useTheme()

    const isDark = resolvedTheme === 'dark'

    const handleToggle = () => {
        setTheme(isDark ? 'light' : 'dark')
    }

    return (
        <div className="mt-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
                {isDark ? (
                    <Moon className="h-5 w-5 text-[#111111] dark:text-[#f4f7fb]" />
                ) : (
                    <Sun className="h-5 w-5 text-[#111111] dark:text-[#f4f7fb]" />
                )}
                <span className="text-sm text-[#666666] dark:text-[#bcc5d3]">
                    {isDark ? '深色模式' : '浅色模式'}
                </span>
            </div>
            <button
                type="button"
                onClick={handleToggle}
                role="switch"
                aria-checked={isDark}
                aria-label="切换深色模式"
                className={[
                    'relative inline-flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-[#111111] focus-visible:ring-offset-2 dark:focus-visible:ring-[#f4f7fb]',
                    isDark
                        ? 'bg-[#364154]'
                        : 'bg-[#CFC5B4]',
                ].join(' ')}
            >
                <span
                    className={[
                        'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition-transform duration-200 ease-in-out dark:bg-[#f4f7fb]',
                        isDark ? 'translate-x-5' : 'translate-x-0',
                    ].join(' ')}
                />
            </button>
        </div>
    )
}

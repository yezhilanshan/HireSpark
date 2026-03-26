'use client'

import { Moon, Sun, Monitor } from 'lucide-react'
import { useTheme } from './ThemeProvider'

export default function ThemeToggle() {
    const { theme, setTheme } = useTheme()

    const toggleTheme = () => {
        if (theme === 'light') {
            setTheme('dark')
        } else if (theme === 'dark') {
            setTheme('system')
        } else {
            setTheme('light')
        }
    }

    const getIcon = () => {
        if (theme === 'light') return <Sun className="w-5 h-5" />
        if (theme === 'dark') return <Moon className="w-5 h-5" />
        return <Monitor className="w-5 h-5" />
    }

    const getLabel = () => {
        if (theme === 'light') return '浅色'
        if (theme === 'dark') return '深色'
        return '跟随系统'
    }

    return (
        <button
            onClick={toggleTheme}
            className="fixed right-4 top-4 z-50 inline-flex items-center gap-2 rounded-xl border border-slate-300/80 bg-white/85 px-4 py-2 text-sm font-semibold text-slate-700 shadow-xl backdrop-blur transition hover:-translate-y-0.5 hover:bg-white dark:border-slate-700 dark:bg-slate-900/80 dark:text-slate-100 dark:hover:bg-slate-900"
            title={`当前主题: ${getLabel()}`}
        >
            {getIcon()}
            <span className="text-sm font-semibold">
                {getLabel()}
            </span>
        </button>
    )
}

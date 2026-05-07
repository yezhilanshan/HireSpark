'use client'

import { Monitor, Moon, Sun } from 'lucide-react'
import { useTheme } from './ThemeProvider'

const OPTIONS = [
    {
        value: 'light',
        label: '浅色',
        description: '适合明亮环境，界面更轻盈清晰。',
        icon: Sun,
    },
    {
        value: 'dark',
        label: '深色',
        description: '适合长时间使用，降低夜间视觉刺激。',
        icon: Moon,
    },
    {
        value: 'system',
        label: '跟随系统',
        description: '自动同步设备当前的外观偏好。',
        icon: Monitor,
    },
] as const

export default function ThemeModeSelector() {
    const { theme, setTheme, resolvedTheme } = useTheme()

    return (
        <div className="grid gap-3 md:grid-cols-3">
            {OPTIONS.map((option) => {
                const Icon = option.icon
                const selected = theme === option.value
                return (
                    <button
                        key={option.value}
                        type="button"
                        onClick={() => setTheme(option.value)}
                        className={[
                            'rounded-2xl border p-4 text-left transition',
                            selected
                                ? 'border-[#111111] bg-[#F3EFE6] shadow-sm dark:border-[#f4f7fb] dark:bg-[#202632]'
                                : 'border-[#E5E5E5] bg-white hover:border-[#CFC5B4] hover:bg-[#FCFBF8] dark:border-[#2d3542] dark:bg-[#181c24] dark:hover:border-[#4b566a] dark:hover:bg-[#1d2330]',
                        ].join(' ')}
                        aria-pressed={selected}
                    >
                        <div className="flex items-center gap-3">
                            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[#E5E5E5] bg-[#FAF9F6] dark:border-[#364154] dark:bg-[#101217]">
                                <Icon className="h-5 w-5 text-[#111111] dark:text-[#f4f7fb]" />
                            </div>
                            <div>
                                <p className="text-sm font-semibold text-[#111111] dark:text-[#f4f7fb]">{option.label}</p>
                                <p className="mt-1 text-xs text-[#7A746B] dark:text-[#9aa7bd]">
                                    {option.value === 'system' ? `当前生效：${resolvedTheme === 'dark' ? '深色' : '浅色'}` : selected ? '当前已启用' : '点击切换'}
                                </p>
                            </div>
                        </div>
                        <p className="mt-4 text-sm leading-6 text-[#666666] dark:text-[#bcc5d3]">{option.description}</p>
                    </button>
                )
            })}
        </div>
    )
}

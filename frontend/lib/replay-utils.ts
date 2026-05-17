/**
 * 复盘页面工具函数统一管理
 * 用于 replay/page.tsx 和 report/page.tsx 共享
 */

/**
 * 安全数字转换
 */
export function safeNumber(value: unknown, fallback = 0): number {
    const numeric = Number(value)
    return Number.isFinite(numeric) ? numeric : fallback
}

/**
 * 数字夹紧
 */
export function clampNumber(value: number, min: number, max: number): number {
    return Math.min(Math.max(value, min), max)
}

/**
 * 将毫秒转换为格式化时间 "MM:SS"
 */
export function formatMs(ms?: number): string {
    const safe = Math.max(0, safeNumber(ms))
    const totalSec = Math.floor(safe / 1000)
    const min = Math.floor(totalSec / 60)
    const sec = totalSec % 60
    return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

/**
 * 获取锚点标签 "第 N 题"
 */
export function anchorLabel(index: number): string {
    return `第 ${index + 1} 题`
}

/**
 * 检查当前时间是否在锚点活跃时间范围内
 */
export function isAnchorActive(
    currentMs: number,
    startMs: number,
    endMs: number
): boolean {
    if (currentMs <= 0) return false
    return currentMs >= Math.max(0, startMs - 500) && currentMs <= endMs + 1000
}

/**
 * 规范化对比文本 - 移除空格并转小写
 */
export function normalizeCompareText(value?: string): string {
    return String(value || '').replace(/\s+/g, '').trim().toLowerCase()
}

/**
 * 维度标签转换
 */
export function dimensionLabel(value?: string): string {
    const normalized = String(value || '').trim().toLowerCase()
    const dimensionMap: Record<string, string> = {
        content: '内容维度',
        delivery: '表达维度',
        presence: '镜头维度',
    }
    return dimensionMap[normalized] || String(value || '待补充维度')
}

/**
 * 轮次标签转换
 */
export function roundLabel(roundType?: string): string {
    const normalized = String(roundType || '').trim().toLowerCase()
    const roundMap: Record<string, string> = {
        technical: '技术基础面',
        project: '项目深度面',
        system_design: '系统设计面',
        hr: 'HR 综合面',
    }
    return roundMap[normalized] || ''
}

/**
 * 格式化时间戳为本地日期字符串
 */
export function formatDate(value?: string): string {
    if (!value) return '未知时间'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return value
    return date.toLocaleString('zh-CN')
}

/**
 * 格式化时长 - 秒数转为 "M分N秒"
 */
export function formatDuration(seconds?: number): string {
    const safe = Math.max(0, Math.round(safeNumber(seconds)))
    if (!safe) return '未记录'
    const min = Math.floor(safe / 60)
    const sec = safe % 60
    if (min <= 0) return `${sec}秒`
    return `${min}分${sec}秒`
}

/**
 * 时间戳转毫秒时间
 */
export function toTime(value?: string): number {
    if (!value) return 0
    const time = new Date(value).getTime()
    return Number.isNaN(time) ? 0 : time
}

/**
 * 判断是否为输入目标（输入框、文本域等）
 */
export function isTypingTarget(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) return false
    if (target.isContentEditable) return true
    const tagName = target.tagName.toLowerCase()
    return tagName === 'input' || tagName === 'textarea' || tagName === 'select'
}

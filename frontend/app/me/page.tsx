'use client'

import Link from 'next/link'
import { ChangeEvent, useCallback, useEffect, useMemo, useState } from 'react'
import {
    Upload,
    FileText,
    Save,
    Trash2,
    RefreshCw,
    CheckCircle,
    AlertCircle,
    Loader2,
    ArrowLeft,
    Wand2,
    Sparkles,
    ArrowRightLeft,
    History,
} from 'lucide-react'
import { getBackendBaseUrl } from '@/lib/backend'

const BACKEND_API_BASE = getBackendBaseUrl()

type ProfileForm = {
    nickname: string
    email: string
    phone: string
    city: string
    targetRole: string
    yearsOfExperience: string
    skills: string
    educationHistory: string
    workExperiences: string
    projectExperiences: string
    intro: string
}

type ParsedResumeData = {
    basic_info?: {
        name?: string
        email?: string
        phone?: string
        city?: string
        target_role?: string
        years_of_experience?: string
        summary?: string
    }
    projects?: Array<{ name: string; technologies: string[]; description: string; responsibilities: string }>
    experiences?: Array<{ company: string; position: string; duration: string; description: string }>
    education?: Array<{ school: string; major: string; degree: string; start_date?: string; end_date?: string }>
    skills?: string[]
    raw_text?: string
}

type ResumeData = {
    id: number
    file_name: string
    file_size: number
    status: 'pending' | 'parsing' | 'parsed' | 'error'
    created_at: string
    parsed_data?: ParsedResumeData
    error_message?: string
}

type ResumeSnapshot = {
    nickname?: string
    target_role?: string
    years_of_experience?: string
    summary: string
    skills: string[]
    education: string
    work_experiences: string
    project_experiences: string
}

type DetailedChange = {
    section: string
    field_label: string
    before: string
    after: string
    reason: string
    impact: string
}

type ExtractedKeywords = {
    required_skills: string[]
    preferred_skills: string[]
    keywords: string[]
    key_responsibilities: string[]
}

type ResumeOptimizationResult = {
    optimization_id: string
    generated_at: string
    strategy: 'nudge' | 'keywords' | 'full'
    target_role: string
    job_description: string
    match_before: number
    match_after: number
    keywords_extracted: ExtractedKeywords
    missing_keywords_before: string[]
    remaining_missing_keywords: string[]
    injected_keywords: string[]
    before_snapshot: ResumeSnapshot
    after_snapshot: ResumeSnapshot
    detailed_changes: DetailedChange[]
    suggestions: string[]
    risks: string[]
    summary: string
    resume_id?: number | null
}

type ResumeOptimizationHistoryItem = {
    optimization_id: string
    created_at: string
    target_role?: string
    strategy?: string
    match_before?: number
    match_after?: number
    resume_file_name?: string
    result?: ResumeOptimizationResult | null
}

const initialForm: ProfileForm = {
    nickname: '候选人',
    email: '',
    phone: '',
    city: '',
    targetRole: 'Java 后端工程师',
    yearsOfExperience: '0-1 年',
    skills: '',
    educationHistory: '',
    workExperiences: '',
    projectExperiences: '',
    intro: '',
}

const optimizationStrategies = [
    {
        id: 'nudge',
        title: '轻量润色',
        description: '只修顺表达，适合快速检查个人简介和项目表述。',
    },
    {
        id: 'keywords',
        title: '关键词增强',
        description: '围绕目标 JD 补齐更贴岗位的关键词和重点表达。',
    },
    {
        id: 'full',
        title: '全面定制',
        description: '综合项目、技能和经历，生成一版更完整的岗位定制建议。',
    },
] as const

function formatEducationHistory(items?: ParsedResumeData['education']): string {
    if (!Array.isArray(items) || items.length === 0) return ''
    return items
        .map((edu) => {
            const school = String(edu.school || '').trim()
            const major = String(edu.major || '').trim()
            const degree = String(edu.degree || '').trim()
            const period = [edu.start_date, edu.end_date].filter(Boolean).join(' - ')
            return [school, major, degree, period ? `(${period})` : ''].filter(Boolean).join(' · ')
        })
        .filter(Boolean)
        .join('\n')
}

function formatWorkExperiences(items?: ParsedResumeData['experiences']): string {
    if (!Array.isArray(items) || items.length === 0) return ''
    return items
        .map((exp) => {
            const company = String(exp.company || '').trim()
            const position = String(exp.position || '').trim()
            const duration = String(exp.duration || '').trim()
            const description = String(exp.description || '').trim()
            const head = [company, position].filter(Boolean).join(' - ')
            const withDuration = [head, duration ? `(${duration})` : ''].filter(Boolean).join(' ')
            return [withDuration, description].filter(Boolean).join('\n')
        })
        .filter(Boolean)
        .join('\n\n')
}

function formatProjectExperiences(items?: ParsedResumeData['projects']): string {
    if (!Array.isArray(items) || items.length === 0) return ''
    return items
        .map((proj) => {
            const name = String(proj.name || '').trim()
            const technologies = Array.isArray(proj.technologies) ? proj.technologies.filter(Boolean).join(', ') : ''
            const description = String(proj.description || '').trim()
            const responsibilities = String(proj.responsibilities || '').trim()
            const lines = [name]
            if (technologies) lines.push(`技术栈：${technologies}`)
            if (description) lines.push(`项目描述：${description}`)
            if (responsibilities) lines.push(`职责：${responsibilities}`)
            return lines.filter(Boolean).join('\n')
        })
        .filter(Boolean)
        .join('\n\n')
}

function buildSnapshotFromForm(form: ProfileForm): ResumeSnapshot {
    return {
        nickname: form.nickname.trim(),
        target_role: form.targetRole.trim(),
        years_of_experience: form.yearsOfExperience.trim(),
        summary: form.intro.trim(),
        skills: form.skills.split(/[,\n，、]/).map((item) => item.trim()).filter(Boolean),
        education: form.educationHistory.trim(),
        work_experiences: form.workExperiences.trim(),
        project_experiences: form.projectExperiences.trim(),
    }
}

function formatStrategyLabel(strategy?: string): string {
    const found = optimizationStrategies.find((item) => item.id === strategy)
    return found?.title || '简历优化'
}

function renderSnapshotSection(title: string, content: string | string[]) {
    const text = Array.isArray(content) ? content.join(', ') : content
    return (
        <div className="rounded-2xl border border-[#ECE7DB] dark:border-[#2d3542] bg-[#FCFBF8] dark:bg-[#151922] p-4">
            <p className="text-xs uppercase tracking-[0.14em] text-[#8D7B5A] dark:text-[#9fb0d0]">{title}</p>
            <div className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[#36322E] dark:text-[#d5ddeb]">
                {text?.trim() ? text : '暂无内容'}
            </div>
        </div>
    )
}

export default function MyPage() {
    const [form, setForm] = useState<ProfileForm>(initialForm)
    const [resumeFile, setResumeFile] = useState<File | null>(null)
    const [savedAt, setSavedAt] = useState<string>('')

    const [uploadedResumes, setUploadedResumes] = useState<ResumeData[]>([])
    const [latestResume, setLatestResume] = useState<ResumeData | null>(null)
    const [isUploading, setIsUploading] = useState(false)
    const [uploadProgress, setUploadProgress] = useState<'idle' | 'uploading' | 'parsing' | 'success' | 'error'>('idle')
    const [uploadError, setUploadError] = useState<string>('')

    const [jobDescription, setJobDescription] = useState('')
    const [optimizationStrategy, setOptimizationStrategy] = useState<'nudge' | 'keywords' | 'full'>('keywords')
    const [optimizationResult, setOptimizationResult] = useState<ResumeOptimizationResult | null>(null)
    const [optimizationHistory, setOptimizationHistory] = useState<ResumeOptimizationHistoryItem[]>([])
    const [isOptimizing, setIsOptimizing] = useState(false)
    const [optimizationError, setOptimizationError] = useState('')
    const [loadingOptimizationId, setLoadingOptimizationId] = useState<string>('')

    const resumeSizeText = useMemo(() => {
        if (!resumeFile) return ''
        const mb = resumeFile.size / (1024 * 1024)
        return `${mb.toFixed(2)} MB`
    }, [resumeFile])

    const currentSnapshot = useMemo(() => buildSnapshotFromForm(form), [form])

    const onFieldChange = (key: keyof ProfileForm, value: string) => {
        setForm((prev) => ({ ...prev, [key]: value }))
    }

    const onSave = () => {
        setSavedAt(new Date().toLocaleString('zh-CN'))
    }

    const onResumeChange = (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        if (!file) return
        setResumeFile(file)
        setUploadError('')
        void handleUpload(file)
    }

    const clearResume = () => {
        setResumeFile(null)
    }

    const safeJson = async (res: Response) => {
        const contentType = res.headers.get('content-type') || ''
        const rawText = await res.text()

        if (!contentType.includes('application/json')) {
            throw new Error(`接口返回非 JSON（HTTP ${res.status}）：${rawText.slice(0, 120)}`)
        }

        try {
            return JSON.parse(rawText)
        } catch {
            throw new Error(`JSON 解析失败（HTTP ${res.status}）：${rawText.slice(0, 120)}`)
        }
    }

    const applyParsedProfileToForm = useCallback((parsed?: ParsedResumeData) => {
        if (!parsed) return

        const rawText = typeof parsed.raw_text === 'string' ? parsed.raw_text : ''
        const emailFromRaw = rawText.match(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/)?.[0] || ''
        const phoneFromRaw = rawText.match(/(?:\+?86[-\s]?)?1[3-9]\d{9}/)?.[0] || ''
        const nameFromRaw =
            rawText.match(/(?:姓名|名字)\s*[:：]\s*([^\n\r,，]+)/)?.[1]?.trim()
            || rawText.match(/候选人\s*[:：]\s*([^\n\r,，]+)/)?.[1]?.trim()
            || ''
        const cityFromRaw =
            rawText.match(/(?:现居|所在城市|期望城市|城市|居住地)\s*[:：]?\s*([^\n\r,，;； ]{2,15})/)?.[1]?.trim()
            || rawText.match(/(北京市|上海市|广州市|深圳市|杭州市|南京市|苏州市|成都市|武汉市|西安市|长沙市|重庆市|天津市|郑州市|青岛市|合肥市|厦门市|福州市|无锡市|宁波市|东莞市|佛山市|珠海市|济南市|昆明市|沈阳市|大连市|北京|上海|广州|深圳|杭州|南京|苏州|成都|武汉|西安|长沙|重庆|天津|郑州|青岛|合肥|厦门|福州|无锡|宁波|东莞|佛山|珠海|济南|昆明|沈阳|大连)/)?.[1]
            || ''

        const educationHistory = formatEducationHistory(parsed.education)
        const workExperiences = formatWorkExperiences(parsed.experiences)
        const projectExperiences = formatProjectExperiences(parsed.projects)

        setForm((prev) => {
            const next = { ...prev }
            const basic = parsed.basic_info || {}

            if (!next.nickname && (basic.name || nameFromRaw)) next.nickname = basic.name || nameFromRaw
            if (next.nickname === initialForm.nickname && (basic.name || nameFromRaw)) next.nickname = basic.name || nameFromRaw
            if (!next.email && (basic.email || emailFromRaw)) next.email = basic.email || emailFromRaw
            if (!next.phone && (basic.phone || phoneFromRaw)) next.phone = basic.phone || phoneFromRaw
            if (!next.city && (basic.city || cityFromRaw)) next.city = basic.city || cityFromRaw
            if (!next.targetRole && basic.target_role) next.targetRole = basic.target_role
            if (next.targetRole === initialForm.targetRole && basic.target_role) next.targetRole = basic.target_role
            if (!next.yearsOfExperience && basic.years_of_experience) next.yearsOfExperience = basic.years_of_experience
            if (next.yearsOfExperience === initialForm.yearsOfExperience && basic.years_of_experience) next.yearsOfExperience = basic.years_of_experience
            if (!next.intro && basic.summary) next.intro = basic.summary

            if (parsed.skills?.length) next.skills = parsed.skills.join(', ')
            if (educationHistory) next.educationHistory = educationHistory
            if (workExperiences) next.workExperiences = workExperiences
            if (projectExperiences) next.projectExperiences = projectExperiences
            return next
        })
    }, [])

    const loadLatestResume = useCallback(async () => {
        try {
            const res = await fetch(`${BACKEND_API_BASE}/api/resume/latest`)
            const data = await safeJson(res)
            if (data.success && data.resume) {
                setLatestResume(data.resume)
                applyParsedProfileToForm(data.resume.parsed_data)
            }
        } catch (error) {
            console.error('加载简历失败:', error)
        }
    }, [applyParsedProfileToForm])

    const loadResumes = useCallback(async () => {
        try {
            const res = await fetch(`${BACKEND_API_BASE}/api/resume?limit=10`)
            const data = await safeJson(res)
            if (data.success) {
                setUploadedResumes(data.resumes)
            }
        } catch (error) {
            console.error('加载简历列表失败:', error)
        }
    }, [])

    const loadOptimizationHistory = useCallback(async () => {
        try {
            const res = await fetch(`${BACKEND_API_BASE}/api/resume/optimizations?limit=8`)
            const data = await safeJson(res)
            if (data.success) {
                setOptimizationHistory(data.optimizations || [])
            }
        } catch (error) {
            console.error('加载简历优化历史失败:', error)
        }
    }, [])

    useEffect(() => {
        void loadLatestResume()
        void loadResumes()
        void loadOptimizationHistory()
    }, [loadLatestResume, loadResumes, loadOptimizationHistory])

    const handleUpload = async (fileOverride?: File) => {
        const file = fileOverride || resumeFile
        if (!file) {
            setUploadError('请选择文件')
            return
        }

        setIsUploading(true)
        setUploadProgress('uploading')
        setUploadError('')

        try {
            const formData = new FormData()
            formData.append('file', file)
            formData.append('user_id', 'default')

            const progressTimer = setTimeout(() => {
                setUploadProgress('parsing')
            }, 700)

            const res = await fetch(`${BACKEND_API_BASE}/api/resume/upload`, {
                method: 'POST',
                body: formData,
            })

            clearTimeout(progressTimer)
            const result = await safeJson(res)

            if (result.success) {
                setUploadProgress('success')
                setLatestResume({
                    id: result.resume_id,
                    file_name: file.name,
                    file_size: file.size,
                    status: 'parsed',
                    created_at: new Date().toISOString(),
                    parsed_data: result.data,
                })
                setResumeFile(null)
                void loadResumes()
                applyParsedProfileToForm(result.data)
            } else {
                setUploadProgress('error')
                setUploadError(result.error || '上传失败')
            }
        } catch (error) {
            setUploadProgress('error')
            setUploadError(error instanceof Error ? error.message : '上传失败，请重试')
            console.error('上传错误:', error)
        } finally {
            setIsUploading(false)
            setTimeout(() => {
                setUploadProgress((prev) => (prev === 'success' ? 'idle' : prev))
            }, 3000)
        }
    }

    const handleReparse = async (resumeId: number) => {
        try {
            const res = await fetch(`${BACKEND_API_BASE}/api/resume/parse`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ resume_id: resumeId }),
            })
            const result = await safeJson(res)
            if (result.success) {
                void loadResumes()
                void loadLatestResume()
                alert('简历重新解析成功')
            } else {
                alert(`重新解析失败：${result.error}`)
            }
        } catch (error) {
            console.error('重新解析失败:', error)
        }
    }

    const handleDelete = async (resumeId: number) => {
        if (!confirm('确定要删除这份简历吗？')) return

        try {
            const res = await fetch(`${BACKEND_API_BASE}/api/resume/${resumeId}`, {
                method: 'DELETE',
            })
            const result = await safeJson(res)
            if (result.success) {
                void loadResumes()
                void loadLatestResume()
            } else {
                alert(`删除失败：${result.error}`)
            }
        } catch (error) {
            console.error('删除失败:', error)
        }
    }

    const handleOptimize = async () => {
        if (!jobDescription.trim()) {
            setOptimizationError('请先粘贴目标岗位的 JD，再开始优化。')
            return
        }

        setIsOptimizing(true)
        setOptimizationError('')
        try {
            const res = await fetch(`${BACKEND_API_BASE}/api/resume/optimize`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: 'default',
                    strategy: optimizationStrategy,
                    job_description: jobDescription.trim(),
                    profile_form: form,
                }),
            })
            const data = await safeJson(res)
            if (!data.success) {
                throw new Error(data.error || '简历优化失败')
            }
            setOptimizationResult(data.result as ResumeOptimizationResult)
            void loadOptimizationHistory()
        } catch (error) {
            setOptimizationError(error instanceof Error ? error.message : '简历优化失败，请稍后重试')
        } finally {
            setIsOptimizing(false)
        }
    }

    const handleLoadOptimization = async (optimizationId: string) => {
        if (!optimizationId) return
        setLoadingOptimizationId(optimizationId)
        try {
            const res = await fetch(`${BACKEND_API_BASE}/api/resume/optimizations/${optimizationId}`)
            const data = await safeJson(res)
            if (!data.success || !data.optimization?.result) {
                throw new Error(data.error || '获取优化详情失败')
            }
            setOptimizationResult(data.optimization.result as ResumeOptimizationResult)
        } catch (error) {
            setOptimizationError(error instanceof Error ? error.message : '获取优化详情失败')
        } finally {
            setLoadingOptimizationId('')
        }
    }

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'parsed':
                return <CheckCircle className="h-5 w-5 text-green-500" />
            case 'parsing':
                return <Loader2 className="h-5 w-5 animate-spin text-[#666666] dark:text-[#bcc5d3]" />
            case 'error':
                return <AlertCircle className="h-5 w-5 text-red-500" />
            default:
                return <FileText className="h-5 w-5 text-[#999999]" />
        }
    }

    const getStatusText = (status: string) => {
        switch (status) {
            case 'parsed':
                return '已解析'
            case 'parsing':
                return '解析中'
            case 'error':
                return '解析失败'
            default:
                return '未知'
        }
    }

    return (
        <main className="page-shell">
            <div className="mb-4">
                <Link
                    href="/settings"
                    className="inline-flex items-center gap-2 rounded-lg border border-[#E5E5E5] bg-white px-3 py-2 text-sm font-medium text-[#111111] transition hover:bg-[#F5F5F5] dark:border-[#2d3542] dark:bg-[#181c24] dark:text-[#f4f7fb] dark:hover:bg-[#2d3542]"
                >
                    <ArrowLeft className="h-4 w-4" />
                    返回系统设置
                </Link>
            </div>

            <div className="mb-6 rounded-3xl border border-[#E5E5E5] bg-[#FAF9F6] p-6 shadow-sm sm:p-8 dark:border-[#2d3542] dark:bg-[#101217]">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-[#999999] dark:text-[#8e98aa]">候选人档案</p>
                <h1 className="mt-2 text-3xl text-[#111111] sm:text-4xl dark:text-[#f4f7fb]">我的简历</h1>
                <p className="mt-2 text-sm text-[#666666] dark:text-[#bcc5d3]">
                    维护候选人资料，上传并解析简历，同时围绕目标岗位做一版可追踪、可对比的简历优化。
                </p>
            </div>

            <section className="grid gap-6">
                <div className="rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm dark:border-[#2d3542] dark:bg-[#181c24]">
                    <div className="mb-4 flex items-center justify-between">
                        <h2 className="text-xl text-[#111111] dark:text-[#f4f7fb]">用户自定义资料</h2>
                        <div className="flex flex-wrap items-center gap-2">
                            <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-[#E5E5E5] bg-white px-4 py-2 text-sm font-medium text-[#111111] transition hover:bg-[#F5F5F5] dark:border-[#2d3542] dark:bg-[#181c24] dark:text-[#f4f7fb] dark:hover:bg-[#2d3542]">
                                <Upload className="h-4 w-4" />
                                上传简历文件
                                <input
                                    type="file"
                                    accept=".pdf,.doc,.docx"
                                    onChange={onResumeChange}
                                    className="hidden"
                                    disabled={isUploading}
                                />
                            </label>
                            <button
                                type="button"
                                onClick={onSave}
                                className="inline-flex items-center gap-2 rounded-lg bg-[#111111] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#222222]"
                            >
                                <Save className="h-4 w-4" />
                                保存资料
                            </button>
                        </div>
                    </div>

                    {uploadProgress === 'uploading' && (
                        <div className="mb-4 flex items-center gap-2 rounded-lg bg-[#F5F5F5] p-3 text-sm text-[#666666] dark:bg-[#2d3542] dark:text-[#bcc5d3]">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            正在上传文件...
                        </div>
                    )}
                    {uploadProgress === 'parsing' && (
                        <div className="mb-4 flex items-center gap-2 rounded-lg bg-[#F5F5F5] p-3 text-sm text-[#666666] dark:bg-[#2d3542] dark:text-[#bcc5d3]">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            正在解析简历内容...
                        </div>
                    )}
                    {uploadProgress === 'success' && (
                        <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 p-3 text-sm text-green-700">
                            <CheckCircle className="h-4 w-4" />
                            简历上传并解析成功，已自动填充到用户自定义资料。
                        </div>
                    )}
                    {uploadProgress === 'error' && (
                        <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                            <AlertCircle className="h-4 w-4" />
                            {uploadError}
                        </div>
                    )}

                    {resumeFile ? (
                        <div className="mb-4 rounded-xl border border-[#E5E5E5] bg-white p-3 dark:border-[#2d3542] dark:bg-[#181c24]">
                            <div className="flex items-start gap-3">
                                <FileText className="mt-0.5 h-5 w-5 text-[#666666] dark:text-[#bcc5d3]" />
                                <div className="min-w-0 flex-1">
                                    <p className="truncate text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">{resumeFile.name}</p>
                                    <p className="text-xs text-[#666666] dark:text-[#bcc5d3]">{resumeSizeText}</p>
                                </div>
                                <button
                                    type="button"
                                    onClick={clearResume}
                                    className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-[#8A3B3B] transition hover:bg-[#F8EEEE]"
                                    disabled={isUploading}
                                    aria-label="移除已选择简历"
                                    title="移除已选择简历"
                                >
                                    <Trash2 className="h-3.5 w-3.5" />
                                </button>
                            </div>
                        </div>
                    ) : (
                        <p className="mb-4 text-sm text-[#666666] dark:text-[#bcc5d3]">尚未选择简历文件</p>
                    )}

                    <div className="grid gap-4 sm:grid-cols-2">
                        <Field label="昵称" value={form.nickname} onChange={(v) => onFieldChange('nickname', v)} />
                        <Field label="邮箱" value={form.email} onChange={(v) => onFieldChange('email', v)} />
                        <Field label="手机号" value={form.phone} onChange={(v) => onFieldChange('phone', v)} />
                        <Field label="所在城市" value={form.city} onChange={(v) => onFieldChange('city', v)} />
                        <Field label="目标岗位" value={form.targetRole} onChange={(v) => onFieldChange('targetRole', v)} />
                        <Field label="工作年限" value={form.yearsOfExperience} onChange={(v) => onFieldChange('yearsOfExperience', v)} />
                    </div>

                    <div className="mt-4 grid gap-4">
                        <Field
                            label="核心技能"
                            value={form.skills}
                            onChange={(v) => onFieldChange('skills', v)}
                            placeholder="例如：Java, Spring Boot, Redis, MySQL"
                        />
                        <AreaField
                            label="学历背景"
                            value={form.educationHistory}
                            onChange={(v) => onFieldChange('educationHistory', v)}
                            placeholder="简历解析后会自动填充学历信息，也可手动编辑"
                            rows={4}
                            minHeightClassName="min-h-[120px]"
                        />
                        <AreaField
                            label="工作经历"
                            value={form.workExperiences}
                            onChange={(v) => onFieldChange('workExperiences', v)}
                            placeholder="简历解析后会自动填充工作经历，也可手动编辑"
                            rows={10}
                            minHeightClassName="min-h-[240px]"
                        />
                        <AreaField
                            label="项目经历"
                            value={form.projectExperiences}
                            onChange={(v) => onFieldChange('projectExperiences', v)}
                            placeholder="简历解析后会自动填充项目经历，也可手动编辑"
                            rows={10}
                            minHeightClassName="min-h-[240px]"
                        />
                        <AreaField
                            label="个人介绍"
                            value={form.intro}
                            onChange={(v) => onFieldChange('intro', v)}
                            placeholder="简要描述你的项目经验、技术栈和求职方向"
                            rows={8}
                            minHeightClassName="min-h-[190px]"
                        />
                    </div>

                    {savedAt ? (
                        <p className="mt-4 rounded-lg bg-[#F5F5F5] px-3 py-2 text-sm text-[#666666] dark:bg-[#2d3542] dark:text-[#bcc5d3]">
                            已保存到前端状态：{savedAt}
                        </p>
                    ) : null}
                </div>

                <div className="rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm dark:border-[#2d3542] dark:bg-[#181c24]">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                            <div className="inline-flex items-center gap-2 rounded-full bg-[#F7F1E3] px-3 py-1 text-xs font-medium text-[#9A6A21] dark:bg-[#252014] dark:text-[#e8c48a]">
                                <Wand2 className="h-3.5 w-3.5" />
                                面向岗位的简历优化
                            </div>
                            <h2 className="mt-3 text-xl text-[#111111] dark:text-[#f4f7fb]">简历优化工作区</h2>
                            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#666666] dark:text-[#bcc5d3]">
                                这部分借鉴 Resume Matcher 的核心方法：先解析目标岗位 JD，再在不编造事实的前提下，围绕摘要、技能、工作经历和项目经历做受控优化，并保留前后对比。
                            </p>
                        </div>
                        {latestResume ? (
                            <div className="rounded-2xl border border-[#ECE7DB] bg-[#FCFBF8] px-4 py-3 text-sm text-[#6A5A3F] dark:border-[#2d3542] dark:bg-[#151922] dark:text-[#c5d0df]">
                                当前解析简历：<span className="font-medium text-[#111111] dark:text-[#f4f7fb]">{latestResume.file_name}</span>
                            </div>
                        ) : (
                            <div className="rounded-2xl border border-[#ECE7DB] bg-[#FCFBF8] px-4 py-3 text-sm text-[#6A5A3F] dark:border-[#2d3542] dark:bg-[#151922] dark:text-[#c5d0df]">
                                还没有解析简历，也可以先基于当前填写的资料做一版优化。
                            </div>
                        )}
                    </div>

                    <div className="mt-6 grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
                        <div className="space-y-4">
                            <AreaField
                                label="目标岗位 JD"
                                value={jobDescription}
                                onChange={setJobDescription}
                                placeholder="粘贴你要投递岗位的真实 JD。建议至少包含岗位职责、技术要求和关键词，这样优化结果会更贴合。"
                                rows={10}
                                minHeightClassName="min-h-[260px]"
                            />

                            <div className="grid gap-3 md:grid-cols-3">
                                {optimizationStrategies.map((strategy) => {
                                    const active = optimizationStrategy === strategy.id
                                    return (
                                        <button
                                            key={strategy.id}
                                            type="button"
                                            onClick={() => setOptimizationStrategy(strategy.id)}
                                            className={`rounded-2xl border p-4 text-left transition ${active
                                                ? 'border-[#111111] bg-[#111111] text-white dark:border-[#f4f7fb] dark:bg-[#f4f7fb] dark:text-[#101217]'
                                                : 'border-[#E5E5E5] bg-[#FCFBF8] text-[#111111] hover:border-[#CFC7B5] dark:border-[#2d3542] dark:bg-[#151922] dark:text-[#f4f7fb] dark:hover:border-[#4b5568]'
                                                }`}
                                        >
                                            <p className="text-sm font-semibold">{strategy.title}</p>
                                            <p className={`mt-2 text-xs leading-5 ${active ? 'text-white/90 dark:text-[#101217]/80' : 'text-[#666666] dark:text-[#bcc5d3]'}`}>
                                                {strategy.description}
                                            </p>
                                        </button>
                                    )
                                })}
                            </div>

                            {optimizationError ? (
                                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                    {optimizationError}
                                </div>
                            ) : null}

                            <button
                                type="button"
                                onClick={handleOptimize}
                                disabled={isOptimizing}
                                className="inline-flex items-center gap-2 rounded-xl bg-[#111111] px-5 py-3 text-sm font-medium text-white transition hover:bg-[#222222] disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                {isOptimizing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                                {isOptimizing ? '正在生成优化建议...' : '开始简历优化'}
                            </button>
                        </div>

                        <div className="rounded-3xl border border-[#ECE7DB] bg-[#FCFBF8] p-5 dark:border-[#2d3542] dark:bg-[#151922]">
                            <div className="flex items-center gap-2 text-[#111111] dark:text-[#f4f7fb]">
                                <History className="h-4 w-4" />
                                <h3 className="text-lg">优化历史</h3>
                            </div>
                            <p className="mt-2 text-sm leading-6 text-[#666666] dark:text-[#bcc5d3]">
                                每次优化都会保存一份快照，方便你回看“优化前后到底改了什么”。
                            </p>
                            <div className="mt-4 space-y-3">
                                {optimizationHistory.length === 0 ? (
                                    <div className="rounded-2xl border border-dashed border-[#D9D2C3] px-4 py-6 text-sm text-[#666666] dark:border-[#3b4454] dark:text-[#bcc5d3]">
                                        还没有简历优化记录。完成一次优化后，这里会显示历史版本。
                                    </div>
                                ) : (
                                    optimizationHistory.map((item) => {
                                        const active = optimizationResult?.optimization_id === item.optimization_id
                                        return (
                                            <button
                                                key={item.optimization_id}
                                                type="button"
                                                onClick={() => void handleLoadOptimization(item.optimization_id)}
                                                className={`w-full rounded-2xl border px-4 py-4 text-left transition ${active
                                                    ? 'border-[#111111] bg-white shadow-sm dark:border-[#f4f7fb] dark:bg-[#1c222d]'
                                                    : 'border-[#E5E5E5] bg-white hover:border-[#CFC7B5] dark:border-[#2d3542] dark:bg-[#181c24] dark:hover:border-[#4b5568]'
                                                    }`}
                                            >
                                                <div className="flex items-start justify-between gap-3">
                                                    <div className="min-w-0">
                                                        <p className="truncate text-sm font-semibold text-[#111111] dark:text-[#f4f7fb]">
                                                            {item.target_role || '未标注目标岗位'}
                                                        </p>
                                                        <p className="mt-1 text-xs text-[#666666] dark:text-[#bcc5d3]">
                                                            {formatStrategyLabel(item.strategy)} · {new Date(item.created_at).toLocaleString('zh-CN')}
                                                        </p>
                                                    </div>
                                                    {loadingOptimizationId === item.optimization_id ? (
                                                        <Loader2 className="mt-1 h-4 w-4 animate-spin text-[#666666] dark:text-[#bcc5d3]" />
                                                    ) : null}
                                                </div>
                                                <div className="mt-3 flex items-center gap-3 text-xs text-[#8A7350] dark:text-[#cdb48a]">
                                                    <span>匹配度 {item.match_before ?? 0} → {item.match_after ?? 0}</span>
                                                    {item.resume_file_name ? <span>来源：{item.resume_file_name}</span> : null}
                                                </div>
                                            </button>
                                        )
                                    })
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {optimizationResult ? (
                    <section className="grid gap-6">
                        <div className="rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm dark:border-[#2d3542] dark:bg-[#181c24]">
                            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                                <div>
                                    <div className="inline-flex items-center gap-2 rounded-full bg-[#F1ECE2] px-3 py-1 text-xs font-medium text-[#8A7350] dark:bg-[#252014] dark:text-[#e8c48a]">
                                        <ArrowRightLeft className="h-3.5 w-3.5" />
                                        优化前后对比
                                    </div>
                                    <h2 className="mt-3 text-xl text-[#111111] dark:text-[#f4f7fb]">本次优化结果</h2>
                                    <p className="mt-2 max-w-3xl text-sm leading-6 text-[#666666] dark:text-[#bcc5d3]">
                                        {optimizationResult.summary || '这版优化重点围绕目标岗位的关键词覆盖、项目表述和个人摘要展开。'}
                                    </p>
                                </div>
                                <div className="rounded-2xl border border-[#ECE7DB] bg-[#FCFBF8] px-4 py-3 text-sm text-[#6A5A3F] dark:border-[#2d3542] dark:bg-[#151922] dark:text-[#c5d0df]">
                                    最近生成：{new Date(optimizationResult.generated_at).toLocaleString('zh-CN')}
                                </div>
                            </div>

                            <div className="mt-6 grid gap-4 md:grid-cols-4">
                                <MetricCard label="优化前匹配度" value={`${optimizationResult.match_before}`} suffix="/100" tone="neutral" />
                                <MetricCard label="优化后匹配度" value={`${optimizationResult.match_after}`} suffix="/100" tone="strong" />
                                <MetricCard label="新增关键词" value={`${optimizationResult.injected_keywords.length}`} suffix="个" tone="accent" />
                                <MetricCard label="仍缺关键词" value={`${optimizationResult.remaining_missing_keywords.length}`} suffix="个" tone="warning" />
                            </div>

                            <div className="mt-6 grid gap-4 xl:grid-cols-2">
                                <div className="rounded-3xl border border-[#E7E0D2] bg-[#FBFAF7] p-5 dark:border-[#2d3542] dark:bg-[#151922]">
                                    <p className="text-sm font-semibold text-[#111111] dark:text-[#f4f7fb]">关键词提取结果</p>
                                    <div className="mt-4 space-y-4">
                                        <KeywordBlock title="必备技能" items={optimizationResult.keywords_extracted.required_skills} />
                                        <KeywordBlock title="优先技能" items={optimizationResult.keywords_extracted.preferred_skills} />
                                        <KeywordBlock title="岗位关键词" items={optimizationResult.keywords_extracted.keywords} />
                                        <KeywordBlock title="优化后新增" items={optimizationResult.injected_keywords} accent />
                                    </div>
                                </div>
                                <div className="rounded-3xl border border-[#E7E0D2] bg-[#FBFAF7] p-5 dark:border-[#2d3542] dark:bg-[#151922]">
                                    <p className="text-sm font-semibold text-[#111111] dark:text-[#f4f7fb]">建议与风险提醒</p>
                                    <div className="mt-4 grid gap-4">
                                        <div>
                                            <p className="text-xs uppercase tracking-[0.14em] text-[#8D7B5A] dark:text-[#9fb0d0]">下一步最值得做</p>
                                            <ul className="mt-3 space-y-2 text-sm leading-6 text-[#36322E] dark:text-[#d5ddeb]">
                                                {(optimizationResult.suggestions.length ? optimizationResult.suggestions : ['建议把最贴目标岗位的项目放在最前面，并补齐结果导向表达。']).map((item) => (
                                                    <li key={item} className="rounded-xl border border-[#EFE6D3] bg-white px-3 py-2 dark:border-[#313b4c] dark:bg-[#1b202a]">
                                                        {item}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                        <div>
                                            <p className="text-xs uppercase tracking-[0.14em] text-[#8D7B5A] dark:text-[#9fb0d0]">需要你确认真实性</p>
                                            <ul className="mt-3 space-y-2 text-sm leading-6 text-[#36322E] dark:text-[#d5ddeb]">
                                                {(optimizationResult.risks.length ? optimizationResult.risks : ['任何新增表达都应确保来源于你真实做过的经历。']).map((item) => (
                                                    <li key={item} className="rounded-xl border border-[#EFE6D3] bg-white px-3 py-2 dark:border-[#313b4c] dark:bg-[#1b202a]">
                                                        {item}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm dark:border-[#2d3542] dark:bg-[#181c24]">
                            <h2 className="text-xl text-[#111111] dark:text-[#f4f7fb]">优化前后预览</h2>
                            <p className="mt-2 text-sm text-[#666666] dark:text-[#bcc5d3]">
                                左边是当前简历快照，右边是建议优化后的表达。第一版先按区块对比，后续我们还可以继续升级成逐句 diff 视图。
                            </p>

                            <div className="mt-6 grid gap-6 xl:grid-cols-2">
                                <div className="space-y-4">
                                    <div className="flex items-center gap-2 text-[#111111] dark:text-[#f4f7fb]">
                                        <FileText className="h-4 w-4" />
                                        <h3 className="text-lg">优化前</h3>
                                    </div>
                                    {renderSnapshotSection('个人介绍', optimizationResult.before_snapshot.summary)}
                                    {renderSnapshotSection('核心技能', optimizationResult.before_snapshot.skills)}
                                    {renderSnapshotSection('学历背景', optimizationResult.before_snapshot.education)}
                                    {renderSnapshotSection('工作经历', optimizationResult.before_snapshot.work_experiences)}
                                    {renderSnapshotSection('项目经历', optimizationResult.before_snapshot.project_experiences)}
                                </div>

                                <div className="space-y-4">
                                    <div className="flex items-center gap-2 text-[#111111] dark:text-[#f4f7fb]">
                                        <Sparkles className="h-4 w-4" />
                                        <h3 className="text-lg">优化后</h3>
                                    </div>
                                    {renderSnapshotSection('个人介绍', optimizationResult.after_snapshot.summary)}
                                    {renderSnapshotSection('核心技能', optimizationResult.after_snapshot.skills)}
                                    {renderSnapshotSection('学历背景', optimizationResult.after_snapshot.education)}
                                    {renderSnapshotSection('工作经历', optimizationResult.after_snapshot.work_experiences)}
                                    {renderSnapshotSection('项目经历', optimizationResult.after_snapshot.project_experiences)}
                                </div>
                            </div>
                        </div>

                        <div className="rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm dark:border-[#2d3542] dark:bg-[#181c24]">
                            <h2 className="text-xl text-[#111111] dark:text-[#f4f7fb]">修改说明</h2>
                            <p className="mt-2 text-sm text-[#666666] dark:text-[#bcc5d3]">
                                这里展示每处重要改动的“改前、改后、为什么这样改”，方便你判断哪些建议值得真正写回正式简历。
                            </p>
                            <div className="mt-6 grid gap-4">
                                {optimizationResult.detailed_changes.length === 0 ? (
                                    <div className="rounded-2xl border border-dashed border-[#D9D2C3] px-4 py-6 text-sm text-[#666666] dark:border-[#3b4454] dark:text-[#bcc5d3]">
                                        当前这版没有生成足够明确的逐项改动，说明原始内容较少或本次优化更偏摘要级润色。
                                    </div>
                                ) : (
                                    optimizationResult.detailed_changes.map((change, index) => (
                                        <div
                                            key={`${change.section}-${change.field_label}-${index}`}
                                            className="rounded-3xl border border-[#EAE3D6] bg-[#FCFBF8] p-5 dark:border-[#2d3542] dark:bg-[#151922]"
                                        >
                                            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                                                <div>
                                                    <p className="text-sm font-semibold text-[#111111] dark:text-[#f4f7fb]">{change.section}</p>
                                                    <p className="mt-1 text-xs uppercase tracking-[0.14em] text-[#8D7B5A] dark:text-[#9fb0d0]">
                                                        {change.field_label}
                                                    </p>
                                                </div>
                                                <span className="inline-flex items-center rounded-full bg-[#F1ECE2] px-3 py-1 text-xs font-medium text-[#8A7350] dark:bg-[#252014] dark:text-[#e8c48a]">
                                                    {change.impact}
                                                </span>
                                            </div>

                                            <div className="mt-4 grid gap-4 xl:grid-cols-2">
                                                <div className="rounded-2xl border border-[#E6DFD0] bg-white p-4 dark:border-[#313b4c] dark:bg-[#1b202a]">
                                                    <p className="text-xs uppercase tracking-[0.14em] text-[#8D7B5A] dark:text-[#9fb0d0]">改前</p>
                                                    <div className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[#36322E] dark:text-[#d5ddeb]">
                                                        {change.before || '原文为空'}
                                                    </div>
                                                </div>
                                                <div className="rounded-2xl border border-[#E6DFD0] bg-white p-4 dark:border-[#313b4c] dark:bg-[#1b202a]">
                                                    <p className="text-xs uppercase tracking-[0.14em] text-[#8D7B5A] dark:text-[#9fb0d0]">改后</p>
                                                    <div className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[#36322E] dark:text-[#d5ddeb]">
                                                        {change.after || '暂无建议'}
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="mt-4 rounded-2xl border border-[#E6DFD0] bg-white px-4 py-3 text-sm leading-6 text-[#5A4B35] dark:border-[#313b4c] dark:bg-[#1b202a] dark:text-[#d5ddeb]">
                                                <span className="font-medium text-[#111111] dark:text-[#f4f7fb]">修改原因：</span>
                                                {change.reason}
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </section>
                ) : null}
            </section>

            {uploadedResumes.length > 0 && (
                <section className="mt-6 rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm dark:border-[#2d3542] dark:bg-[#181c24]">
                    <h2 className="mb-4 text-xl text-[#111111] dark:text-[#f4f7fb]">简历历史</h2>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-[#E5E5E5] dark:border-[#2d3542]">
                                    <th className="py-2 text-left font-medium text-[#111111] dark:text-[#f4f7fb]">文件名</th>
                                    <th className="py-2 text-left font-medium text-[#111111] dark:text-[#f4f7fb]">大小</th>
                                    <th className="py-2 text-left font-medium text-[#111111] dark:text-[#f4f7fb]">状态</th>
                                    <th className="py-2 text-left font-medium text-[#111111] dark:text-[#f4f7fb]">上传时间</th>
                                    <th className="py-2 text-right font-medium text-[#111111] dark:text-[#f4f7fb]">操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {uploadedResumes.map((resume) => (
                                    <tr key={resume.id} className="border-b border-[#ECEAE3] last:border-0 dark:border-[#2d3542]">
                                        <td className="py-3">
                                            <div className="flex items-center gap-2">
                                                {getStatusIcon(resume.status)}
                                                <span className="font-medium text-[#111111] dark:text-[#f4f7fb]">{resume.file_name}</span>
                                            </div>
                                            {resume.error_message ? (
                                                <p className="mt-1 text-xs text-red-500">{resume.error_message}</p>
                                            ) : null}
                                        </td>
                                        <td className="py-3 text-[#666666] dark:text-[#bcc5d3]">
                                            {(resume.file_size / (1024 * 1024)).toFixed(2)} MB
                                        </td>
                                        <td className="py-3">
                                            <span className={`rounded px-2 py-0.5 text-xs ${resume.status === 'parsed'
                                                ? 'bg-green-100 text-green-700'
                                                : resume.status === 'parsing'
                                                    ? 'bg-[#F5F5F5] text-[#666666] dark:bg-[#2d3542] dark:text-[#bcc5d3]'
                                                    : 'bg-red-100 text-red-700'
                                                }`}>
                                                {getStatusText(resume.status)}
                                            </span>
                                        </td>
                                        <td className="py-3 text-[#666666] dark:text-[#bcc5d3]">
                                            {new Date(resume.created_at).toLocaleString('zh-CN')}
                                        </td>
                                        <td className="py-3">
                                            <div className="flex justify-end gap-2">
                                                <button
                                                    onClick={() => void handleReparse(resume.id)}
                                                    className="rounded p-1 text-[#666666] hover:bg-[#F5F5F5] hover:text-[#111111] dark:text-[#bcc5d3] dark:hover:bg-[#2d3542] dark:hover:text-[#f4f7fb]"
                                                    title="重新解析"
                                                >
                                                    <RefreshCw className="h-4 w-4" />
                                                </button>
                                                <button
                                                    onClick={() => void handleDelete(resume.id)}
                                                    className="rounded p-1 text-[#666666] hover:bg-[#F8EEEE] hover:text-[#8A3B3B] dark:text-[#bcc5d3] dark:hover:bg-[#2d3542] dark:hover:text-[#f4f7fb]"
                                                    title="删除"
                                                >
                                                    <Trash2 className="h-4 w-4" />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>
            )}
        </main>
    )
}

function MetricCard({
    label,
    value,
    suffix,
    tone = 'neutral',
}: {
    label: string
    value: string
    suffix: string
    tone?: 'neutral' | 'strong' | 'accent' | 'warning'
}) {
    const toneClassMap = {
        neutral: 'bg-[#FCFBF8] border-[#EAE3D6] text-[#111111]',
        strong: 'bg-[#111111] border-[#111111] text-white',
        accent: 'bg-[#F4F8F1] border-[#D7E5D0] text-[#215A2E]',
        warning: 'bg-[#FFF8EC] border-[#F1D596] text-[#9A6A21]',
    }
    return (
        <div className={`rounded-3xl border p-5 ${toneClassMap[tone]} dark:border-[#2d3542] dark:bg-[#151922] dark:text-[#f4f7fb]`}>
            <p className="text-sm opacity-75">{label}</p>
            <div className="mt-3 flex items-end gap-1">
                <span className="text-3xl font-semibold">{value}</span>
                <span className="pb-1 text-sm opacity-70">{suffix}</span>
            </div>
        </div>
    )
}

function KeywordBlock({ title, items, accent = false }: { title: string; items: string[]; accent?: boolean }) {
    return (
        <div>
            <p className="text-xs uppercase tracking-[0.14em] text-[#8D7B5A] dark:text-[#9fb0d0]">{title}</p>
            <div className="mt-3 flex flex-wrap gap-2">
                {items.length === 0 ? (
                    <span className="text-sm text-[#8E8471] dark:text-[#b5c0d2]">暂无</span>
                ) : (
                    items.map((item) => (
                        <span
                            key={item}
                            className={`rounded-full px-3 py-1 text-xs font-medium ${accent
                                ? 'bg-[#111111] text-white dark:bg-[#f4f7fb] dark:text-[#101217]'
                                : 'bg-white text-[#5D503C] dark:bg-[#1b202a] dark:text-[#d5ddeb]'
                                }`}
                        >
                            {item}
                        </span>
                    ))
                )}
            </div>
        </div>
    )
}

type FieldProps = {
    label: string
    value: string
    onChange: (value: string) => void
    placeholder?: string
}

function Field({ label, value, onChange, placeholder }: FieldProps) {
    return (
        <label className="grid gap-1.5 text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">
            <span>{label}</span>
            <input
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
                className="rounded-lg border border-[#E5E5E5] bg-white px-3 py-2 text-[#111111] outline-none transition focus:border-[#111111] dark:border-[#2d3542] dark:bg-[#181c24] dark:text-[#f4f7fb] dark:focus:border-[#f4f7fb]"
            />
        </label>
    )
}

type AreaFieldProps = {
    label: string
    value: string
    onChange: (value: string) => void
    placeholder?: string
    rows?: number
    minHeightClassName?: string
}

function AreaField({ label, value, onChange, placeholder, rows = 8, minHeightClassName = 'min-h-[190px]' }: AreaFieldProps) {
    return (
        <label className="grid gap-1.5 text-sm font-medium text-[#111111] dark:text-[#f4f7fb]">
            <span>{label}</span>
            <textarea
                rows={rows}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
                className={`${minHeightClassName} resize-y rounded-lg border border-[#E5E5E5] bg-white px-3 py-2 text-[#111111] outline-none transition focus:border-[#111111] dark:border-[#2d3542] dark:bg-[#181c24] dark:text-[#f4f7fb] dark:focus:border-[#f4f7fb]`}
            />
        </label>
    )
}

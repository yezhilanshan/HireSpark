'use client'

import { useMemo, useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { Upload, FileText, Save, Trash2, ArrowLeft, RefreshCw, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'

const BACKEND_API_BASE = (process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000').replace(/\/$/, '')

type ProfileForm = {
    nickname: string
    email: string
    phone: string
    city: string
    targetRole: string
    yearsOfExperience: string
    skills: string
    intro: string
}

type ResumeData = {
    id: number
    file_name: string
    file_size: number
    status: 'pending' | 'parsing' | 'parsed' | 'error'
    created_at: string
    parsed_data?: {
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
    error_message?: string
}

const initialForm: ProfileForm = {
    nickname: '候选人',
    email: '',
    phone: '',
    city: '',
    targetRole: 'Java 后端工程师',
    yearsOfExperience: '0-1 年',
    skills: '',
    intro: '',
}

export default function MyPage() {
    const [form, setForm] = useState<ProfileForm>(initialForm)
    const [resumeFile, setResumeFile] = useState<File | null>(null)
    const [savedAt, setSavedAt] = useState<string>('')

    // 简历相关状态
    const [uploadedResumes, setUploadedResumes] = useState<ResumeData[]>([])
    const [latestResume, setLatestResume] = useState<ResumeData | null>(null)
    const [isUploading, setIsUploading] = useState(false)
    const [uploadProgress, setUploadProgress] = useState<'idle' | 'uploading' | 'parsing' | 'success' | 'error'>('idle')
    const [uploadError, setUploadError] = useState<string>('')
    const [isDragOver, setIsDragOver] = useState(false)

    const resumeSizeText = useMemo(() => {
        if (!resumeFile) return ''
        const mb = resumeFile.size / (1024 * 1024)
        return `${mb.toFixed(2)} MB`
    }, [resumeFile])

    const onFieldChange = (key: keyof ProfileForm, value: string) => {
        setForm(prev => ({ ...prev, [key]: value }))
    }

    const onSave = () => {
        setSavedAt(new Date().toLocaleString('zh-CN'))
    }

    const onResumeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        if (!file) return
        setResumeFile(file)
        setUploadError('')
    }

    const onDropResume = (event: React.DragEvent<HTMLLabelElement>) => {
        event.preventDefault()
        event.stopPropagation()
        setIsDragOver(false)

        const file = event.dataTransfer.files?.[0]
        if (!file) return
        setResumeFile(file)
        setUploadError('')
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

    const applyParsedProfileToForm = useCallback((parsed?: ResumeData['parsed_data']) => {
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

        setForm(prev => {
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

            if (parsed.skills?.length) {
                next.skills = parsed.skills.join(', ')
            }

            return next
        })
    }, [])

    // 加载最新简历
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

    // 加载简历列表
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

    useEffect(() => {
        loadLatestResume()
        loadResumes()
    }, [loadLatestResume, loadResumes])

    const handleUpload = async () => {
        if (!resumeFile) {
            setUploadError('请选择文件')
            return
        }

        setIsUploading(true)
        setUploadProgress('uploading')
        setUploadError('')

        try {
            const formData = new FormData()
            formData.append('file', resumeFile)
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
                    file_name: resumeFile.name,
                    file_size: resumeFile.size,
                    status: 'parsed',
                    created_at: new Date().toISOString(),
                    parsed_data: result.data,
                })
                // 清空文件选择
                setResumeFile(null)
                // 刷新列表
                loadResumes()
                // 填充表单
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
            // 3 秒后重置状态
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
                loadResumes()
                loadLatestResume()
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
                loadResumes()
                loadLatestResume()
            } else {
                alert(`删除失败：${result.error}`)
            }
        } catch (error) {
            console.error('删除失败:', error)
        }
    }

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'parsed':
                return <CheckCircle className="h-5 w-5 text-green-500" />
            case 'parsing':
                return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
            case 'error':
                return <AlertCircle className="h-5 w-5 text-red-500" />
            default:
                return <FileText className="h-5 w-5 text-gray-400" />
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
        <main className="min-h-screen bg-[radial-gradient(circle_at_top_right,_#ccfbf1_0%,_#dbeafe_40%,_#f8fafc_100%)] p-4 text-slate-800 transition-colors dark:bg-[radial-gradient(circle_at_top_right,_#0f172a_0%,_#111827_45%,_#030712_100%)] dark:text-slate-100 sm:p-8">
            <div className="mx-auto max-w-6xl">
                <div className="mb-6 flex flex-wrap items-center gap-3">
                    <h1 className="text-2xl font-black tracking-tight sm:text-3xl">我的信息</h1>
                    <Link
                        href="/"
                        className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium shadow-sm transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:hover:bg-slate-800"
                    >
                        <ArrowLeft className="h-4 w-4" />
                        返回首页
                    </Link>
                </div>

                <section className="grid gap-6 lg:grid-cols-3">
                    {/* 左侧：用户资料 */}
                    <div className="rounded-2xl border border-white/70 bg-white/85 p-6 shadow-xl backdrop-blur dark:border-slate-700 dark:bg-slate-900/70 lg:col-span-2">
                        <div className="mb-4 flex items-center justify-between">
                            <h2 className="text-xl font-bold">用户自定义资料</h2>
                            <button
                                type="button"
                                onClick={onSave}
                                className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-700"
                            >
                                <Save className="h-4 w-4" />
                                保存资料
                            </button>
                        </div>

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
                                label="个人介绍"
                                value={form.intro}
                                onChange={(v) => onFieldChange('intro', v)}
                                placeholder="简要描述你的项目经验、技术栈和求职方向"
                            />
                        </div>

                        {savedAt ? (
                            <p className="mt-4 rounded-lg bg-teal-50 px-3 py-2 text-sm text-teal-700 dark:bg-teal-900/30 dark:text-teal-300">
                                已保存到前端状态：{savedAt}
                            </p>
                        ) : null}
                    </div>

                    {/* 右侧：简历上传 */}
                    <div className="rounded-2xl border border-white/70 bg-white/85 p-6 shadow-xl backdrop-blur dark:border-slate-700 dark:bg-slate-900/70">
                        <h2 className="mb-4 text-xl font-bold">添加简历文档</h2>

                        {/* 上传状态提示 */}
                        {uploadProgress === 'uploading' && (
                            <div className="mb-4 flex items-center gap-2 rounded-lg bg-blue-50 p-3 text-sm text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                正在上传文件...
                            </div>
                        )}
                        {uploadProgress === 'parsing' && (
                            <div className="mb-4 flex items-center gap-2 rounded-lg bg-purple-50 p-3 text-sm text-purple-700 dark:bg-purple-900/30 dark:text-purple-300">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                正在解析简历内容...
                            </div>
                        )}
                        {uploadProgress === 'success' && (
                            <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 p-3 text-sm text-green-700 dark:bg-green-900/30 dark:text-green-300">
                                <CheckCircle className="h-4 w-4" />
                                简历上传并解析成功！
                            </div>
                        )}
                        {uploadProgress === 'error' && (
                            <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
                                <AlertCircle className="h-4 w-4" />
                                {uploadError}
                            </div>
                        )}

                        <label
                            onDragEnter={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                setIsDragOver(true)
                            }}
                            onDragOver={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                setIsDragOver(true)
                            }}
                            onDragLeave={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                setIsDragOver(false)
                            }}
                            onDrop={onDropResume}
                            className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition dark:bg-slate-800 ${isDragOver
                                    ? 'border-teal-500 bg-teal-50 dark:border-teal-400 dark:bg-slate-700'
                                    : 'border-slate-300 bg-slate-50 hover:border-teal-400 hover:bg-teal-50 dark:border-slate-600 dark:hover:border-teal-500 dark:hover:bg-slate-700'
                                }`}
                        >
                            <Upload className="mb-2 h-7 w-7 text-teal-600 dark:text-teal-300" />
                            <span className="whitespace-nowrap text-sm font-medium">点击上传简历（PDF/DOC/DOCX）</span>
                            <span className="mt-1 text-xs text-slate-500">支持拖拽文件到此区域，AI 自动识别项目经历与技术栈</span>
                            <input
                                type="file"
                                accept=".pdf,.doc,.docx"
                                onChange={onResumeChange}
                                className="hidden"
                                disabled={isUploading}
                            />
                        </label>

                        {resumeFile ? (
                            <div className="mt-4 space-y-3">
                                <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                                    <div className="flex items-start gap-3">
                                        <FileText className="mt-0.5 h-5 w-5 text-indigo-600 dark:text-indigo-300" />
                                        <div className="min-w-0 flex-1">
                                            <p className="truncate text-sm font-medium">{resumeFile.name}</p>
                                            <p className="text-xs text-slate-500">{resumeSizeText}</p>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={clearResume}
                                            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-rose-600 transition hover:bg-rose-50 dark:text-rose-300 dark:hover:bg-rose-900/30"
                                            disabled={isUploading}
                                        >
                                            <Trash2 className="h-3.5 w-3.5" />
                                        </button>
                                    </div>
                                </div>
                                <button
                                    onClick={handleUpload}
                                    disabled={isUploading}
                                    className="w-full rounded-lg bg-teal-600 py-2 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:bg-teal-400"
                                >
                                    {isUploading ? '上传中...' : '上传并解析'}
                                </button>
                            </div>
                        ) : (
                            <p className="mt-4 text-sm text-slate-500">尚未选择简历文件</p>
                        )}

                        {/* 最新解析结果 */}
                        {latestResume?.parsed_data && (
                            <div className="mt-6 border-t border-slate-200 pt-4 dark:border-slate-700">
                                <h3 className="mb-3 text-sm font-bold">简历解析结果</h3>

                                {/* 教育经历 - 支持多个 */}
                                {latestResume.parsed_data.education && latestResume.parsed_data.education.length > 0 && (
                                    <div className="mb-3 rounded-lg bg-slate-50 p-2 text-xs dark:bg-slate-800">
                                        <span className="font-semibold">学历：</span>
                                        <div className="mt-1 space-y-1">
                                            {latestResume.parsed_data.education.map((edu, idx) => (
                                                <div key={idx}>
                                                    <span className="font-medium">{edu.school}</span>
                                                    {edu.major && ` · ${edu.major}`}
                                                    {edu.degree && ` · ${edu.degree}`}
                                                    {(edu.start_date || edu.end_date) && ` (${edu.start_date || ''} - ${edu.end_date || ''})`}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {latestResume.parsed_data.skills && latestResume.parsed_data.skills.length > 0 && (
                                    <div className="mb-3">
                                        <span className="text-xs font-semibold">技术栈：</span>
                                        <div className="mt-1 flex flex-wrap gap-1">
                                            {latestResume.parsed_data.skills.slice(0, 10).map((skill, i) => (
                                                <span key={i} className="rounded bg-indigo-100 px-2 py-0.5 text-xs text-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-300">
                                                    {skill}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {latestResume.parsed_data.experiences && latestResume.parsed_data.experiences.length > 0 && (
                                    <div className="mb-2">
                                        <span className="text-xs font-semibold">工作经历：</span>
                                        <div className="mt-1 space-y-1">
                                            {latestResume.parsed_data.experiences.slice(0, 3).map((exp, i) => (
                                                <div key={i} className="text-xs text-slate-600 dark:text-slate-400">
                                                    <span className="font-medium">{exp.company}</span>
                                                    {exp.position && ` - ${exp.position}`}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {latestResume.parsed_data.projects && latestResume.parsed_data.projects.length > 0 && (
                                    <div>
                                        <span className="text-xs font-semibold">项目经验：</span>
                                        <div className="mt-1 space-y-1">
                                            {latestResume.parsed_data.projects.slice(0, 3).map((proj, i) => (
                                                <div key={i} className="text-xs text-slate-600 dark:text-slate-400">
                                                    <span className="font-medium">{proj.name}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </section>

                {/* 简历历史列表 */}
                {uploadedResumes.length > 0 && (
                    <section className="mt-6 rounded-2xl border border-white/70 bg-white/85 p-6 shadow-xl backdrop-blur dark:border-slate-700 dark:bg-slate-900/70">
                        <h2 className="mb-4 text-xl font-bold">简历历史</h2>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-slate-200 dark:border-slate-700">
                                        <th className="py-2 text-left font-semibold">文件名</th>
                                        <th className="py-2 text-left font-semibold">大小</th>
                                        <th className="py-2 text-left font-semibold">状态</th>
                                        <th className="py-2 text-left font-semibold">上传时间</th>
                                        <th className="py-2 text-right font-semibold">操作</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {uploadedResumes.map((resume) => (
                                        <tr key={resume.id} className="border-b border-slate-100 last:border-0 dark:border-slate-800">
                                            <td className="py-3">
                                                <div className="flex items-center gap-2">
                                                    {getStatusIcon(resume.status)}
                                                    <span className="font-medium">{resume.file_name}</span>
                                                </div>
                                                {resume.error_message && (
                                                    <p className="mt-1 text-xs text-red-500">{resume.error_message}</p>
                                                )}
                                            </td>
                                            <td className="py-3 text-slate-500">
                                                {(resume.file_size / (1024 * 1024)).toFixed(2)} MB
                                            </td>
                                            <td className="py-3">
                                                <span className={`rounded px-2 py-0.5 text-xs ${resume.status === 'parsed' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
                                                        resume.status === 'parsing' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' :
                                                            'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                                                    }`}>
                                                    {getStatusText(resume.status)}
                                                </span>
                                            </td>
                                            <td className="py-3 text-slate-500">
                                                {new Date(resume.created_at).toLocaleString('zh-CN')}
                                            </td>
                                            <td className="py-3">
                                                <div className="flex justify-end gap-2">
                                                    <button
                                                        onClick={() => handleReparse(resume.id)}
                                                        className="rounded p-1 text-slate-500 hover:bg-slate-100 hover:text-teal-600 dark:hover:bg-slate-800"
                                                        title="重新解析"
                                                    >
                                                        <RefreshCw className="h-4 w-4" />
                                                    </button>
                                                    <button
                                                        onClick={() => handleDelete(resume.id)}
                                                        className="rounded p-1 text-slate-500 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-900/30"
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
            </div>
        </main>
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
        <label className="grid gap-1.5 text-sm font-medium">
            <span>{label}</span>
            <input
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-200 dark:border-slate-700 dark:bg-slate-900 dark:focus:border-teal-400 dark:focus:ring-teal-900"
            />
        </label>
    )
}

type AreaFieldProps = {
    label: string
    value: string
    onChange: (value: string) => void
    placeholder?: string
}

function AreaField({ label, value, onChange, placeholder }: AreaFieldProps) {
    return (
        <label className="grid gap-1.5 text-sm font-medium">
            <span>{label}</span>
            <textarea
                rows={5}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
                className="resize-y rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-200 dark:border-slate-700 dark:bg-slate-900 dark:focus:border-teal-400 dark:focus:ring-teal-900"
            />
        </label>
    )
}

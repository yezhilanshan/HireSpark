'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Upload, FileText, Save, Trash2, RefreshCw, CheckCircle, AlertCircle, Loader2, ArrowLeft } from 'lucide-react'
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
                setResumeFile(null)
                loadResumes()
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
                return <Loader2 className="h-5 w-5 text-[#666666] animate-spin" />
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
                    className="inline-flex items-center gap-2 rounded-lg border border-[#E5E5E5] bg-white px-3 py-2 text-sm font-medium text-[#111111] transition hover:bg-[#F5F5F5]"
                >
                    <ArrowLeft className="h-4 w-4" />
                    返回系统设置
                </Link>
            </div>
            <div className="mb-6 rounded-3xl border border-[#E5E5E5] bg-[#FAF9F6] p-6 shadow-sm sm:p-8">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-[#999999]">候选人档案</p>
                <h1 className="mt-2 text-3xl text-[#111111] sm:text-4xl">我的信息与简历</h1>
                <p className="mt-2 text-sm text-[#666666]">维护候选人资料，并通过简历解析自动补全关键信息。</p>
            </div>

            <section className="grid gap-6 lg:grid-cols-3">
                <div className="rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm lg:col-span-2">
                    <div className="mb-4 flex items-center justify-between">
                        <h2 className="text-xl text-[#111111]">用户自定义资料</h2>
                        <button
                            type="button"
                            onClick={onSave}
                            className="inline-flex items-center gap-2 rounded-lg bg-[#111111] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#222222]"
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
                        <p className="mt-4 rounded-lg bg-[#F5F5F5] px-3 py-2 text-sm text-[#666666]">
                            已保存到前端状态：{savedAt}
                        </p>
                    ) : null}
                </div>

                <div className="rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                    <h2 className="mb-4 text-xl text-[#111111]">添加简历文档</h2>

                    {uploadProgress === 'uploading' && (
                        <div className="mb-4 flex items-center gap-2 rounded-lg bg-[#F5F5F5] p-3 text-sm text-[#666666]">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            正在上传文件...
                        </div>
                    )}
                    {uploadProgress === 'parsing' && (
                        <div className="mb-4 flex items-center gap-2 rounded-lg bg-[#F5F5F5] p-3 text-sm text-[#666666]">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            正在解析简历内容...
                        </div>
                    )}
                    {uploadProgress === 'success' && (
                        <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 p-3 text-sm text-green-700">
                            <CheckCircle className="h-4 w-4" />
                            简历上传并解析成功！
                        </div>
                    )}
                    {uploadProgress === 'error' && (
                        <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700">
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
                        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition ${
                            isDragOver
                                ? 'border-[#111111] bg-[#F5F5F5]'
                                : 'border-[#E5E5E5] bg-[#FAF9F6] hover:border-[#111111] hover:bg-[#F5F5F5]'
                        }`}
                    >
                        <Upload className="mb-2 h-7 w-7 text-[#111111]" />
                        <span className="whitespace-nowrap text-sm font-medium text-[#111111]">点击上传简历（PDF/DOC/DOCX）</span>
                        <span className="mt-1 text-xs text-[#666666]">支持拖拽文件到此区域，AI 自动识别项目经历与技术栈</span>
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
                            <div className="rounded-xl border border-[#E5E5E5] bg-white p-3">
                                <div className="flex items-start gap-3">
                                    <FileText className="mt-0.5 h-5 w-5 text-[#666666]" />
                                    <div className="min-w-0 flex-1">
                                        <p className="truncate text-sm font-medium text-[#111111]">{resumeFile.name}</p>
                                        <p className="text-xs text-[#666666]">{resumeSizeText}</p>
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
                            <button
                                onClick={handleUpload}
                                disabled={isUploading}
                                className="w-full rounded-lg bg-[#111111] py-2 text-sm font-medium text-white transition hover:bg-[#222222] disabled:cursor-not-allowed disabled:bg-[#C8C2B7]"
                            >
                                {isUploading ? '上传中...' : '上传并解析'}
                            </button>
                        </div>
                    ) : (
                        <p className="mt-4 text-sm text-[#666666]">尚未选择简历文件</p>
                    )}

                    {latestResume?.parsed_data && (
                        <div className="mt-6 border-t border-[#E5E5E5] pt-4">
                            <h3 className="mb-3 text-sm font-medium text-[#111111]">简历解析结果</h3>

                            {latestResume.parsed_data.education && latestResume.parsed_data.education.length > 0 && (
                                <div className="mb-3 rounded-lg bg-[#FAF9F6] p-2 text-xs text-[#333333]">
                                    <span className="font-medium">学历：</span>
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
                                    <span className="text-xs font-medium text-[#111111]">技术栈：</span>
                                    <div className="mt-1 flex flex-wrap gap-1">
                                        {latestResume.parsed_data.skills.slice(0, 10).map((skill, i) => (
                                            <span key={i} className="rounded bg-[#F5F5F5] px-2 py-0.5 text-xs text-[#555555]">
                                                {skill}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {latestResume.parsed_data.experiences && latestResume.parsed_data.experiences.length > 0 && (
                                <div className="mb-2">
                                    <span className="text-xs font-medium text-[#111111]">工作经历：</span>
                                    <div className="mt-1 space-y-1">
                                        {latestResume.parsed_data.experiences.slice(0, 3).map((exp, i) => (
                                            <div key={i} className="text-xs text-[#666666]">
                                                <span className="font-medium text-[#333333]">{exp.company}</span>
                                                {exp.position && ` - ${exp.position}`}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {latestResume.parsed_data.projects && latestResume.parsed_data.projects.length > 0 && (
                                <div>
                                    <span className="text-xs font-medium text-[#111111]">项目经验：</span>
                                    <div className="mt-1 space-y-1">
                                        {latestResume.parsed_data.projects.slice(0, 3).map((proj, i) => (
                                            <div key={i} className="text-xs text-[#666666]">
                                                <span className="font-medium text-[#333333]">{proj.name}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </section>

            {uploadedResumes.length > 0 && (
                <section className="mt-6 rounded-2xl border border-[#E5E5E5] bg-white p-6 shadow-sm">
                    <h2 className="mb-4 text-xl text-[#111111]">简历历史</h2>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-[#E5E5E5]">
                                    <th className="py-2 text-left font-medium text-[#111111]">文件名</th>
                                    <th className="py-2 text-left font-medium text-[#111111]">大小</th>
                                    <th className="py-2 text-left font-medium text-[#111111]">状态</th>
                                    <th className="py-2 text-left font-medium text-[#111111]">上传时间</th>
                                    <th className="py-2 text-right font-medium text-[#111111]">操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {uploadedResumes.map((resume) => (
                                    <tr key={resume.id} className="border-b border-[#ECEAE3] last:border-0">
                                        <td className="py-3">
                                            <div className="flex items-center gap-2">
                                                {getStatusIcon(resume.status)}
                                                <span className="font-medium text-[#111111]">{resume.file_name}</span>
                                            </div>
                                            {resume.error_message && (
                                                <p className="mt-1 text-xs text-red-500">{resume.error_message}</p>
                                            )}
                                        </td>
                                        <td className="py-3 text-[#666666]">
                                            {(resume.file_size / (1024 * 1024)).toFixed(2)} MB
                                        </td>
                                        <td className="py-3">
                                            <span className={`rounded px-2 py-0.5 text-xs ${
                                                resume.status === 'parsed'
                                                    ? 'bg-green-100 text-green-700'
                                                    : resume.status === 'parsing'
                                                        ? 'bg-[#F5F5F5] text-[#666666]'
                                                        : 'bg-red-100 text-red-700'
                                            }`}>
                                                {getStatusText(resume.status)}
                                            </span>
                                        </td>
                                        <td className="py-3 text-[#666666]">
                                            {new Date(resume.created_at).toLocaleString('zh-CN')}
                                        </td>
                                        <td className="py-3">
                                            <div className="flex justify-end gap-2">
                                                <button
                                                    onClick={() => handleReparse(resume.id)}
                                                    className="rounded p-1 text-[#666666] hover:bg-[#F5F5F5] hover:text-[#111111]"
                                                    title="重新解析"
                                                >
                                                    <RefreshCw className="h-4 w-4" />
                                                </button>
                                                <button
                                                    onClick={() => handleDelete(resume.id)}
                                                    className="rounded p-1 text-[#666666] hover:bg-[#F8EEEE] hover:text-[#8A3B3B]"
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

type FieldProps = {
    label: string
    value: string
    onChange: (value: string) => void
    placeholder?: string
}

function Field({ label, value, onChange, placeholder }: FieldProps) {
    return (
        <label className="grid gap-1.5 text-sm font-medium text-[#111111]">
            <span>{label}</span>
            <input
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
                className="rounded-lg border border-[#E5E5E5] bg-white px-3 py-2 text-[#111111] outline-none transition focus:border-[#111111]"
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
        <label className="grid gap-1.5 text-sm font-medium text-[#111111]">
            <span>{label}</span>
            <textarea
                rows={5}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
                className="resize-y rounded-lg border border-[#E5E5E5] bg-white px-3 py-2 text-[#111111] outline-none transition focus:border-[#111111]"
            />
        </label>
    )
}

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, Loader2, ArrowRight, ArrowLeft, Check, User, BookOpen, Target, FileText } from 'lucide-react'
import { api } from '../api/client'
import { PROVINCES } from '../constants'
import type { DecisionResult } from '../types'

const MATH_OPTIONS = ['数学一', '数学二', '数学三', '不考数学']
const ENGLISH_OPTIONS = ['英语一', '英语二']
const SCORE_RANGES = [
  { label: '<300', value: 280 },
  { label: '300–350', value: 325 },
  { label: '350–400', value: 375 },
  { label: '400–450', value: 425 },
  { label: '450+', value: 475 },
]
const EXAM_YEARS = [2026, 2027, 2028]
const STRENGTHS = ['强', '中', '弱']
const LEVELS = ['C9', '985', '211', '双一流', '普本']

type FormData = {
  nickname: string
  undergraduate_school: string
  undergraduate_major: string
  target_province: string
  target_level: string
  estimated_score: number | null
  exam_year: number | null
  exam_config_math: string
  exam_config_english: string
  math_strength: string
  english_strength: string
}

const INITIAL: FormData = {
  nickname: '',
  undergraduate_school: '',
  undergraduate_major: '',
  target_province: '',
  target_level: '',
  estimated_score: null,
  exam_year: null,
  exam_config_math: '',
  exam_config_english: '',
  math_strength: '',
  english_strength: '',
}

const STEP_ICONS = [User, BookOpen, Target, FileText]
const STEP_LABELS = ['称呼', '本科背景', '目标与分数', '考试科目']
const STEP_TITLES = [
  '应该怎么称呼你？',
  '你的本科背景是？',
  '你的考研目标是什么？',
  '你的考试科目和强弱项？',
]

function isValidStep(step: number, f: FormData): boolean {
  switch (step) {
    case 0: return f.nickname.trim().length >= 1
    case 1: return f.undergraduate_school.trim().length >= 1 && f.undergraduate_major.trim().length >= 1
    case 2: return !!f.target_level && !!f.estimated_score && !!f.exam_year
    case 3: return !!f.exam_config_math && !!f.exam_config_english &&
      !!f.english_strength && (f.exam_config_math === '不考数学' || !!f.math_strength)
    default: return false
  }
}

export default function OnboardingPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [form, setForm] = useState<FormData>(INITIAL)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function update<K extends keyof FormData>(key: K, value: FormData[K]) {
    setForm(prev => ({ ...prev, [key]: value }))
    setError(null)
  }

  function next() {
    if (step < 3) setStep(step + 1)
  }

  function prev() {
    if (step > 0) setStep(step - 1)
  }

  async function handleSubmit() {
    setSubmitting(true)
    setError(null)

    try {
      const examConfig: Record<string, string> = {}
      if (form.exam_config_math) examConfig.math = form.exam_config_math
      if (form.exam_config_english) examConfig.english = form.exam_config_english

      const strengths: Record<string, string> = {}
      if (form.english_strength) strengths.英语 = form.english_strength
      if (form.math_strength && form.exam_config_math !== '不考数学') strengths.数学 = form.math_strength

      const profileRes = await api.profiles.create({
        nickname: form.nickname.trim(),
        undergraduate_school: form.undergraduate_school.trim() || undefined,
        undergraduate_major: form.undergraduate_major.trim() || undefined,
        target_province: form.target_province,
        target_level: form.target_level,
        estimated_score: form.estimated_score,
        exam_year: form.exam_year,
        exam_config: JSON.stringify(examConfig),
        subject_strengths: JSON.stringify(strengths),
      })

      if (!profileRes.success || !profileRes.data) {
        throw new Error(profileRes.error || '画像创建失败')
      }

      const pid = profileRes.data.id
      localStorage.setItem('study_profile_id', String(pid))

      const recRes = await api.decisions.recommend({
        profile_id: pid,
        target_province: form.target_province,
        target_level: form.target_level,
      })

      if (!recRes.success || !recRes.data) {
        throw new Error(recRes.error || '推荐生成失败')
      }

      const result: DecisionResult = recRes.data
      if (result.recommendations.length === 0) {
        // Still navigate — DecisionPage shows "no results" state gracefully
      }

      sessionStorage.setItem('onboarding_result', JSON.stringify(result))
      navigate('/decisions', { state: { fromOnboarding: true } })
    } catch (e) {
      setError(e instanceof Error ? e.message : '未知错误，请重试')
      setSubmitting(false)
    }
  }

  // ── Submitting state: loading animation ──
  if (submitting) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center px-4">
        <div className="text-center max-w-md">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-blue-50 mb-6">
            <Loader2 className="w-10 h-10 text-blue-600 animate-spin" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">正在为你生成智能推荐...</h2>
          <p className="text-sm text-slate-500">
            我们正在分析你的画像，匹配全国院校数据库，
            筛选最适合你的考研目标院校。
          </p>
        </div>
      </div>
    )
  }

  // ── Step renderer ──
  return (
    <div className="min-h-[70vh] flex items-start justify-center px-4 pt-8 sm:pt-16">
      <div className="w-full max-w-lg">
        {/* Progress bar */}
        <div className="flex items-center gap-1 mb-10">
          {STEP_LABELS.map((label, i) => {
            const Icon = STEP_ICONS[i]
            const done = i < step
            const current = i === step
            return (
              <div key={label} className="flex-1 flex flex-col items-center">
                <div className={`w-9 h-9 rounded-full flex items-center justify-center mb-1.5 transition-colors ${
                  done ? 'bg-blue-600 text-white' :
                  current ? 'bg-blue-600 text-white ring-4 ring-blue-100' :
                  'bg-slate-100 text-slate-400'
                }`}>
                  {done ? <Check className="w-4 h-4" /> : <Icon className="w-4 h-4" />}
                </div>
                <span className={`text-xs font-medium ${
                  current ? 'text-blue-700' : done ? 'text-blue-600' : 'text-slate-400'
                }`}>{label}</span>
              </div>
            )
          })}
        </div>

        {/* Title */}
        <h2 className="text-2xl font-bold text-slate-900 mb-8 text-center">
          {STEP_TITLES[step]}
        </h2>

        {/* Error */}
        {error && (
          <div className="mb-6 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Step 0: Nickname */}
        {step === 0 && (
          <div className="space-y-4">
            <input
              type="text"
              value={form.nickname}
              onChange={e => update('nickname', e.target.value)}
              onKeyDown={e => e.key === 'Enter' && isValidStep(0, form) && next()}
              placeholder="输入你的昵称..."
              autoFocus
              className="w-full text-lg px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
            />
          </div>
        )}

        {/* Step 1: Undergraduate background */}
        {step === 1 && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">本科院校</label>
              <input
                type="text"
                value={form.undergraduate_school}
                onChange={e => update('undergraduate_school', e.target.value)}
                placeholder="如：北京大学"
                className="w-full px-4 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">本科专业</label>
              <input
                type="text"
                value={form.undergraduate_major}
                onChange={e => update('undergraduate_major', e.target.value)}
                placeholder="如：计算机科学与技术"
                className="w-full px-4 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
              />
            </div>
          </div>
        )}

        {/* Step 2: Targets */}
        {step === 2 && (
          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">目标省份</label>
              <select
                value={form.target_province}
                onChange={e => update('target_province', e.target.value)}
                className="w-full px-4 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none bg-white transition"
              >
                <option value="">不限（全国范围）</option>
                {PROVINCES.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">目标院校层次</label>
              <div className="flex flex-wrap gap-2">
                {LEVELS.map(l => (
                  <button
                    key={l}
                    type="button"
                    onClick={() => update('target_level', l)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium border transition ${
                      form.target_level === l
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-slate-700 border-slate-300 hover:border-blue-400'
                    }`}
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">预估分数</label>
              <div className="flex flex-wrap gap-2">
                {SCORE_RANGES.map(s => (
                  <button
                    key={s.label}
                    type="button"
                    onClick={() => update('estimated_score', s.value)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium border transition ${
                      form.estimated_score === s.value
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-slate-700 border-slate-300 hover:border-blue-400'
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">考试年份</label>
              <div className="flex flex-wrap gap-2">
                {EXAM_YEARS.map(y => (
                  <button
                    key={y}
                    type="button"
                    onClick={() => update('exam_year', y)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium border transition ${
                      form.exam_year === y
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-slate-700 border-slate-300 hover:border-blue-400'
                    }`}
                  >
                    {y}年
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Exam subjects & strengths */}
        {step === 3 && (
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">数学科目</label>
              <div className="flex flex-wrap gap-2">
                {MATH_OPTIONS.map(m => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => {
                      update('exam_config_math', m)
                      if (m === '不考数学') update('math_strength', '')
                    }}
                    className={`px-4 py-2 rounded-lg text-sm font-medium border transition ${
                      form.exam_config_math === m
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-slate-700 border-slate-300 hover:border-blue-400'
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">英语科目</label>
              <div className="flex gap-2">
                {ENGLISH_OPTIONS.map(e => (
                  <button
                    key={e}
                    type="button"
                    onClick={() => update('exam_config_english', e)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium border transition ${
                      form.exam_config_english === e
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-slate-700 border-slate-300 hover:border-blue-400'
                    }`}
                  >
                    {e}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">英语强弱</label>
              <div className="flex gap-3">
                {STRENGTHS.map(s => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => update('english_strength', s)}
                    className={`px-5 py-2 rounded-lg text-sm font-medium border transition ${
                      form.english_strength === s
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-slate-700 border-slate-300 hover:border-blue-400'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {form.exam_config_math && form.exam_config_math !== '不考数学' && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">数学强弱</label>
                <div className="flex gap-3">
                  {STRENGTHS.map(s => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => update('math_strength', s)}
                      className={`px-5 py-2 rounded-lg text-sm font-medium border transition ${
                        form.math_strength === s
                          ? 'bg-blue-600 text-white border-blue-600'
                          : 'bg-white text-slate-700 border-slate-300 hover:border-blue-400'
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Navigation buttons */}
        <div className="flex justify-between mt-10">
          <button
            type="button"
            onClick={prev}
            disabled={step === 0}
            className={`inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-medium transition ${
              step === 0
                ? 'text-slate-300 cursor-not-allowed'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <ArrowLeft className="w-4 h-4" />
            上一步
          </button>

          {step < 3 ? (
            <button
              type="button"
              onClick={next}
              disabled={!isValidStep(step, form)}
              className={`inline-flex items-center gap-1.5 px-5 py-2.5 rounded-lg text-sm font-medium transition ${
                isValidStep(step, form)
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-slate-200 text-slate-400 cursor-not-allowed'
              }`}
            >
              下一步
              <ArrowRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!isValidStep(step, form)}
              className={`inline-flex items-center gap-1.5 px-5 py-2.5 rounded-lg text-sm font-medium transition ${
                isValidStep(step, form)
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-slate-200 text-slate-400 cursor-not-allowed'
              }`}
            >
              查看推荐
              <Sparkles className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Footer text */}
        <p className="text-center text-xs text-slate-400 mt-6">
          以上信息将用于生成个性化院校推荐，后续可随时在「画像」中修改
        </p>
      </div>
    </div>
  )
}

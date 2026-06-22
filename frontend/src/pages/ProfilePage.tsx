import { useState, useEffect } from 'react'
import {
  Plus, Trash2, Edit3, Check, User, Save,
} from 'lucide-react'
import { api } from '../api/client'
import { PROVINCES, SCHOOL_LEVELS } from '../constants'
import type { UserProfile } from '../types'

interface ProfileForm {
  nickname: string
  undergraduate_school: string
  undergraduate_major: string
  target_province: string
  target_level: string
  estimated_score: number | ''
  available_hours_per_day: number | ''
  exam_year: number | ''
  notes: string
  exam_config_math: string
  exam_config_english: string
  exam_config_politics: string
  exam_config_major: string
}

function emptyForm(): ProfileForm {
  return {
    nickname: '',
    undergraduate_school: '',
    undergraduate_major: '',
    target_province: '',
    target_level: '',
    estimated_score: '',
    available_hours_per_day: '',
    exam_year: new Date().getFullYear() + 1,
    notes: '',
    exam_config_math: '',
    exam_config_english: '',
    exam_config_politics: '',
    exam_config_major: '',
  }
}

function profileToForm(p: UserProfile): ProfileForm {
  return {
    nickname: p.nickname || '',
    undergraduate_school: p.undergraduate_school || '',
    undergraduate_major: p.undergraduate_major || '',
    target_province: p.target_province || '',
    target_level: p.target_level || '',
    estimated_score: p.estimated_score ?? '',
    available_hours_per_day: p.available_hours_per_day ?? '',
    exam_year: p.exam_year ?? '',
    notes: p.notes || '',
    exam_config_math: p.exam_config?.math || '',
    exam_config_english: p.exam_config?.english || '',
    exam_config_politics: p.exam_config?.politics || '',
    exam_config_major: p.exam_config?.['专业课'] || '',
  }
}

function formToPayload(f: ProfileForm) {
  const exam_config: Record<string, string> = {}
  if (f.exam_config_math) exam_config.math = f.exam_config_math
  if (f.exam_config_english) exam_config.english = f.exam_config_english
  if (f.exam_config_politics) exam_config.politics = f.exam_config_politics
  if (f.exam_config_major) exam_config['专业课'] = f.exam_config_major

  return {
    nickname: f.nickname,
    undergraduate_school: f.undergraduate_school || null,
    undergraduate_major: f.undergraduate_major || null,
    target_province: f.target_province || null,
    target_level: f.target_level || null,
    estimated_score: f.estimated_score || null,
    available_hours_per_day: f.available_hours_per_day || null,
    exam_year: f.exam_year || null,
    notes: f.notes || null,
    exam_config: Object.keys(exam_config).length > 0 ? JSON.stringify(exam_config) : null,
  }
}

export default function ProfilePage() {
  const [profiles, setProfiles] = useState<UserProfile[]>([])
  const [editingId, setEditingId] = useState<number | 'new' | null>(null)
  const [form, setForm] = useState<ProfileForm>(emptyForm())
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeProfileId, setActiveProfileId] = useState(
    () => localStorage.getItem('study_profile_id') || ''
  )

  useEffect(() => { loadProfiles() }, [])

  async function loadProfiles() {
    try {
      const res = await api.profiles.list()
      if (res.success && res.data) {
        setProfiles(res.data.items || [])
      }
    } catch { console.error('Failed to load profiles') }
  }

  function startCreate() {
    setForm(emptyForm())
    setEditingId('new')
    setError(null)
  }

  function startEdit(p: UserProfile) {
    setForm(profileToForm(p))
    setEditingId(p.id)
    setError(null)
  }

  function cancelEdit() {
    setEditingId(null)
    setError(null)
  }

  function updateField(field: keyof ProfileForm, value: string | number) {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  async function handleSave() {
    if (!form.nickname.trim()) {
      setError('昵称不能为空')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const payload = formToPayload(form)
      if (editingId === 'new') {
        const res = await api.profiles.create(payload)
        if (res.success) {
          await loadProfiles()
          cancelEdit()
        } else {
          setError(res.error || '创建失败')
        }
      } else if (typeof editingId === 'number') {
        const res = await api.profiles.update(editingId, payload)
        if (res.success) {
          await loadProfiles()
          cancelEdit()
        } else {
          setError(res.error || '更新失败')
        }
      }
    } catch (err) {
      console.error('Failed to save profile:', err)
      setError('保存失败，请检查网络连接')
    }
    setSaving(false)
  }

  async function handleDelete(id: number) {
    if (!confirm('确定要删除这个画像吗？')) return
    try {
      const res = await api.profiles.delete(id)
      if (res.success) {
        if (String(id) === activeProfileId) {
          localStorage.removeItem('study_profile_id')
          setActiveProfileId('')
        }
        await loadProfiles()
      } else {
        setError(res.error || '删除失败')
      }
    } catch {
      setError('删除失败，请检查网络连接')
    }
  }

  function selectProfile(id: number) {
    localStorage.setItem('study_profile_id', String(id))
    setActiveProfileId(String(id))
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 mb-1">考生画像管理</h1>
          <p className="text-sm text-slate-500">创建和管理你的考研个人画像</p>
        </div>
        <button
          onClick={startCreate}
          disabled={editingId !== null}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-40 transition-colors text-sm font-medium"
        >
          <Plus className="w-4 h-4" />
          新建画像
        </button>
      </div>

      {/* Profile list */}
      {profiles.length === 0 && editingId !== 'new' && (
        <div className="text-center py-12 text-slate-400">
          <User className="w-12 h-12 mx-auto mb-3 text-slate-300" />
          <p>还没有考生画像，点击"新建画像"开始</p>
        </div>
      )}

      <div className="space-y-3">
        {profiles.map(p => (
          <div
            key={p.id}
            className={`bg-white rounded-xl border p-5 transition-all ${
              String(p.id) === activeProfileId
                ? 'border-purple-400 ring-2 ring-purple-100'
                : 'border-slate-200'
            }`}
          >
            {editingId === p.id ? (
              <ProfileForm
                form={form}
                onChange={updateField}
                onSave={handleSave}
                onCancel={cancelEdit}
                saving={saving}
                error={error}
              />
            ) : (
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-slate-900">{p.nickname}</h3>
                    {String(p.id) === activeProfileId && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-purple-50 border border-purple-200 rounded text-purple-700">
                        当前使用
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400 mb-2">
                    {[p.undergraduate_school, p.target_level, p.estimated_score ? `${p.estimated_score}分` : '']
                      .filter(Boolean).join(' · ') || '未填写详细信息'}
                  </p>
                  {(p.exam_config?.math || p.exam_config?.english || p.exam_config?.专业课) && (
                    <div className="flex flex-wrap gap-1">
                      {p.exam_config?.math && (
                        <span className="text-xs px-1.5 py-0.5 bg-purple-50 border border-purple-200 rounded text-purple-700">{p.exam_config.math}</span>
                      )}
                      {p.exam_config?.english && (
                        <span className="text-xs px-1.5 py-0.5 bg-blue-50 border border-blue-200 rounded text-blue-700">{p.exam_config.english}</span>
                      )}
                      {p.exam_config?.专业课 && (
                        <span className="text-xs px-1.5 py-0.5 bg-indigo-50 border border-indigo-200 rounded text-indigo-700">{p.exam_config.专业课}</span>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {String(p.id) !== activeProfileId && (
                    <button
                      onClick={() => selectProfile(p.id)}
                      className="p-1.5 text-xs text-purple-600 hover:bg-purple-50 rounded transition-colors"
                      title="设为当前画像"
                    >
                      <Check className="w-4 h-4" />
                    </button>
                  )}
                  <button
                    onClick={() => startEdit(p)}
                    className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded transition-colors"
                    title="编辑"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleDelete(p.id)}
                    className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                    title="删除"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* New profile form */}
      {editingId === 'new' && (
        <div className="bg-white rounded-xl border-2 border-purple-300 p-5 mt-3">
          <ProfileForm
            form={form}
            onChange={updateField}
            onSave={handleSave}
            onCancel={cancelEdit}
            saving={saving}
            error={error}
          />
        </div>
      )}
    </div>
  )
}

function ProfileForm({
  form, onChange, onSave, onCancel, saving, error,
}: {
  form: ProfileForm
  onChange: (f: keyof ProfileForm, v: string | number) => void
  onSave: () => void
  onCancel: () => void
  saving: boolean
  error: string | null
}) {
  return (
    <div className="space-y-4">
      {error && (
        <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">昵称 *</label>
          <input
            type="text"
            value={form.nickname}
            onChange={e => onChange('nickname', e.target.value)}
            className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 outline-none"
            placeholder="如：张三-计算机考研"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">预估分数</label>
          <input
            type="number"
            value={form.estimated_score}
            onChange={e => onChange('estimated_score', e.target.value ? Number(e.target.value) : '')}
            className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 outline-none"
            placeholder="如：350"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">本科院校</label>
          <input
            type="text"
            value={form.undergraduate_school}
            onChange={e => onChange('undergraduate_school', e.target.value)}
            className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 outline-none"
            placeholder="如：河北大学"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">本科专业</label>
          <input
            type="text"
            value={form.undergraduate_major}
            onChange={e => onChange('undergraduate_major', e.target.value)}
            className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 outline-none"
            placeholder="如：计算机科学与技术"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">目标省份</label>
          <select
            value={form.target_province}
            onChange={e => onChange('target_province', e.target.value)}
            className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 outline-none"
          >
            <option value="">不限</option>
            {PROVINCES.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">目标层次</label>
          <select
            value={form.target_level}
            onChange={e => onChange('target_level', e.target.value)}
            className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 outline-none"
          >
            <option value="">不限</option>
            {SCHOOL_LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">考研年份</label>
          <input
            type="number"
            value={form.exam_year}
            onChange={e => onChange('exam_year', e.target.value ? Number(e.target.value) : '')}
            className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 outline-none"
            placeholder="如：2026"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">每日备考时间（小时）</label>
          <input
            type="number"
            value={form.available_hours_per_day}
            onChange={e => onChange('available_hours_per_day', e.target.value ? Number(e.target.value) : '')}
            className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 outline-none"
            placeholder="如：6"
            min={0}
            max={16}
          />
        </div>
      </div>

      {/* Exam config */}
      <div>
        <label className="block text-xs font-medium text-slate-600 mb-2">考试科目</label>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div>
            <input
              type="text"
              value={form.exam_config_math}
              onChange={e => onChange('exam_config_math', e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 outline-none"
              placeholder="数学（如：数学一）"
            />
          </div>
          <div>
            <input
              type="text"
              value={form.exam_config_english}
              onChange={e => onChange('exam_config_english', e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 outline-none"
              placeholder="英语（如：英语一）"
            />
          </div>
          <div>
            <input
              type="text"
              value={form.exam_config_politics}
              onChange={e => onChange('exam_config_politics', e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 outline-none"
              placeholder="政治"
            />
          </div>
          <div>
            <input
              type="text"
              value={form.exam_config_major}
              onChange={e => onChange('exam_config_major', e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 outline-none"
              placeholder="专业课"
            />
          </div>
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-600 mb-1">备注</label>
        <textarea
          value={form.notes}
          onChange={e => onChange('notes', e.target.value)}
          className="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-purple-500 outline-none resize-none"
          placeholder="其他补充信息..."
          rows={2}
        />
      </div>

      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={onSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors text-sm font-medium"
        >
          <Save className="w-3.5 h-3.5" />
          {saving ? '保存中...' : '保存'}
        </button>
        <button
          onClick={onCancel}
          disabled={saving}
          className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
        >
          取消
        </button>
      </div>
    </div>
  )
}

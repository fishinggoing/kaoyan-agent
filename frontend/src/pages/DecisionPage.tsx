import { useState, useEffect, useRef, useMemo } from 'react'
import { useSearchParams, useLocation } from 'react-router-dom'
import {
  Target, AlertCircle, Loader2, ChevronDown,
  TrendingUp, ShieldCheck, ThumbsUp, AlertTriangle,
  Lightbulb,
} from 'lucide-react'
import { api } from '../api/client'
import { PROVINCES, SCHOOL_LEVELS } from '../constants'
import type { UserProfile, DecisionResult, Recommendation } from '../types'
import RecommendationCard from '../components/RecommendationCard'

const TIER_CONFIG: { key: string; label: string; color: string; bg: string; icon: typeof Target }[] = [
  { key: '冲刺', label: '冲刺院校', color: 'text-orange-600', bg: 'bg-orange-50 border-orange-200', icon: AlertTriangle },
  { key: '稳妥', label: '稳妥院校', color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200', icon: ShieldCheck },
  { key: '保底', label: '保底院校', color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200', icon: ThumbsUp },
]

function groupByTier(recommendations: Recommendation[]): Map<string, Recommendation[]> {
  const map = new Map<string, Recommendation[]>()
  for (const r of recommendations) {
    const tier = r.risk_level || '稳妥'
    if (!map.has(tier)) map.set(tier, [])
    map.get(tier)!.push(r)
  }
  return map
}

function extractTags(result: DecisionResult): { advantages: string[]; warnings: string[]; trends: string[] } {
  const advantages: string[] = []
  const warnings: string[] = []
  const trends: string[] = []

  // Collect from all recommendations
  for (const rec of result.recommendations) {
    for (const p of rec.pros) {
      if (!advantages.includes(p)) advantages.push(p)
    }
    for (const c of rec.cons) {
      if (!warnings.includes(c)) warnings.push(c)
    }
  }

  // Extract trend keywords from score_trend texts
  const trendTexts = result.recommendations.map(r => r.score_trend).filter(Boolean)
  const trendKeywords = new Set<string>()
  for (const t of trendTexts) {
    if (t.includes('上涨') || t.includes('上升')) trendKeywords.add('分数上涨')
    if (t.includes('下降') || t.includes('降低')) trendKeywords.add('分数下降')
    if (t.includes('稳定') || t.includes('持平')) trendKeywords.add('分数稳定')
    if (t.includes('波动')) trendKeywords.add('分数波动')
    if (t.includes('竞争') && t.includes('激烈')) trendKeywords.add('竞争激烈')
  }
  trends.push(...Array.from(trendKeywords))

  // Extract from analysis text key phrases
  if (result.analysis) {
    const analysis = result.analysis
    if (analysis.includes('优势') || analysis.includes('强项')) {
      const sentences = analysis.split(/[。；;]/)
      for (const s of sentences) {
        if ((s.includes('优势') || s.includes('突出') || s.includes('实力')) && s.length < 40) {
          const cleaned = s.replace(/^[^，。；;]*[，。；;]?\s*/, '').trim()
          if (cleaned.length > 4 && cleaned.length < 40 && !advantages.includes(cleaned)) {
            advantages.push(cleaned)
          }
        }
      }
    }
  }

  return {
    advantages: advantages.slice(0, 8),
    warnings: warnings.slice(0, 6),
    trends: trends.slice(0, 4),
  }
}

export default function DecisionPage() {
  const [searchParams] = useSearchParams()
  const location = useLocation()

  const urlProvince = searchParams.get('province') || ''
  const urlLevel = searchParams.get('level') || ''
  const urlMajor = searchParams.get('major') || ''
  const urlSchools = (searchParams.get('schools') || '').split(',').filter(Boolean)

  const [profiles, setProfiles] = useState<UserProfile[]>([])
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [profileId, setProfileId] = useState<string>(
    () => localStorage.getItem('study_profile_id') || ''
  )
  const [targetProvince, setTargetProvince] = useState(urlProvince)
  const [targetLevel, setTargetLevel] = useState(urlLevel)
  const [majorKeyword, setMajorKeyword] = useState(urlMajor)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<DecisionResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showFilters, setShowFilters] = useState(false)

  useEffect(() => { loadProfileList() }, [])
  useEffect(() => { loadProfile() }, [profileId])

  const lastSearchKey = useRef('')

  useEffect(() => {
    if (!location.state?.fromOnboarding) return
    const cached = sessionStorage.getItem('onboarding_result')
    if (!cached) return
    try {
      const data = JSON.parse(cached) as DecisionResult
      setResult(data)
      lastSearchKey.current = '__onboarding__'
      sessionStorage.removeItem('onboarding_result')
      window.history.replaceState({}, '')
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    if (!profile || !profileId) return
    const searchKey = [urlSchools.join(','), urlProvince, urlLevel, urlMajor].join('|')
    if (searchKey === lastSearchKey.current) return
    lastSearchKey.current = searchKey
    handleRecommend()
  }, [profile, profileId, urlSchools.join(','), urlProvince, urlLevel, urlMajor])

  async function loadProfileList() {
    try {
      const res = await api.profiles.list()
      if (res.success && res.data) setProfiles(res.data.items || [])
    } catch { console.error('Failed to load profile list') }
  }

  async function loadProfile() {
    if (!profileId) return
    try {
      const res = await api.profiles.get(Number(profileId))
      if (res.success && res.data) {
        setProfile(res.data)
        if (urlProvince || urlLevel || urlMajor) {
          if (urlProvince) setTargetProvince(urlProvince)
          if (urlLevel) setTargetLevel(urlLevel)
          if (urlMajor) setMajorKeyword(urlMajor)
          return
        }
        const pw = res.data.preference_weights
        if (pw) {
          setTargetProvince(pw.preferred_cities?.length ? pw.preferred_cities[0] : '')
          setTargetLevel('')
          setMajorKeyword(pw.preferred_majors?.length ? pw.preferred_majors[0] : '')
        } else {
          setTargetProvince(res.data.target_province || '')
          setTargetLevel(res.data.target_level || '')
          setMajorKeyword('')
        }
      }
    } catch (err) {
      console.error('Failed to load profile:', err)
      setProfile(null)
    }
  }

  async function handleRecommend() {
    if (!profileId) { setError('请先选择个人资料'); return }
    setError(null)
    setResult(null)
    setLoading(true)
    try {
      const useChatSchools = urlSchools.length > 0
      const res = useChatSchools
        ? await api.decisions.fromChat({
            profile_id: Number(profileId), school_names: urlSchools,
            target_province: targetProvince || undefined,
            target_level: targetLevel || undefined,
            major_keyword: majorKeyword || undefined,
          })
        : await api.decisions.recommend({
            profile_id: Number(profileId),
            target_province: targetProvince || undefined,
            target_level: targetLevel || undefined,
            major_keyword: majorKeyword || undefined,
          })
      if (res.success && res.data) {
        setResult(res.data)
      } else {
        setError(res.error || '推荐生成失败')
      }
    } catch {
      setError('请求失败，请检查网络连接')
    }
    setLoading(false)
  }

  const tierGroups = useMemo(() => result ? groupByTier(result.recommendations) : new Map(), [result])
  const tags = useMemo(() => result ? extractTags(result) : null, [result])

  // ---- Loading state ----
  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center">
        <Loader2 className="w-10 h-10 mx-auto mb-4 text-blue-600 animate-spin" />
        <h2 className="text-lg font-semibold text-slate-700 mb-2">正在匹配院校</h2>
        <p className="text-sm text-slate-500">综合分析你的条件与全国院校数据，请稍候...</p>
      </div>
    )
  }

  // ---- Results view ----
  if (result && result.recommendations.length > 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6">
        {/* Page header - compact */}
        <div className="mb-6">
          <h1 className="text-xl font-bold text-slate-900">根据你的情况推荐以下院校</h1>
          <p className="text-sm text-slate-500 mt-1">
            共推荐 <span className="font-semibold text-slate-700">{result.recommendations.length}</span> 个目标院校
            {profile && <> · 基于「{profile.nickname}」</>}
          </p>
        </div>

        {/* Tier summary bar */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          {TIER_CONFIG.map(({ key, label, color, bg, icon: Icon }) => {
            const count = tierGroups.get(key)?.length || 0
            return (
              <div key={key} className={`${bg} border rounded-lg p-3 text-center ${count ? '' : 'opacity-40'}`}>
                <div className={`text-lg font-bold ${color}`}>{count}</div>
                <div className={`text-xs ${color} flex items-center justify-center gap-1 mt-0.5`}>
                  <Icon className="w-3 h-3" />{label}
                </div>
              </div>
            )
          })}
        </div>

        {/* Results by tier */}
        {TIER_CONFIG.map(({ key, label, color, icon: Icon }) => {
          const items = tierGroups.get(key)
          if (!items || items.length === 0) return null
          return (
            <section key={key} className="mb-6">
              <h2 className={`text-sm font-semibold mb-3 flex items-center gap-1.5 ${color}`}>
                <Icon className="w-4 h-4" />{label}
                <span className="text-slate-400 font-normal">({items.length})</span>
              </h2>
              <div className="space-y-3">
                {items.map((rec, idx) => (
                  <RecommendationCard key={`${key}-${idx}`} rec={rec} index={idx} />
                ))}
              </div>
            </section>
          )
        })}

        {/* Tag-based analysis section */}
        {tags && (tags.advantages.length > 0 || tags.warnings.length > 0 || tags.trends.length > 0) && (
          <div className="bg-white rounded-lg border border-slate-200 p-5 mb-6">
            <h3 className="font-semibold text-slate-900 mb-3 text-sm flex items-center gap-2">
              <Lightbulb className="w-4 h-4 text-amber-500" />
              匹配分析
            </h3>

            {tags.trends.length > 0 && (
              <div className="mb-3">
                <div className="text-xs text-slate-400 mb-1.5 flex items-center gap-1">
                  <TrendingUp className="w-3 h-3" />整体趋势
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {tags.trends.map(t => (
                    <span key={t} className="text-xs px-2 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-100">{t}</span>
                  ))}
                </div>
              </div>
            )}

            {tags.advantages.length > 0 && (
              <div className="mb-3">
                <div className="text-xs text-slate-400 mb-1.5">匹配优势</div>
                <div className="flex flex-wrap gap-1.5">
                  {tags.advantages.map(t => (
                    <span key={t} className="text-xs px-2 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100">{t}</span>
                  ))}
                </div>
              </div>
            )}

            {tags.warnings.length > 0 && (
              <div>
                <div className="text-xs text-slate-400 mb-1.5">需要注意</div>
                <div className="flex flex-wrap gap-1.5">
                  {tags.warnings.map(t => (
                    <span key={t} className="text-xs px-2 py-1 rounded-full bg-orange-50 text-orange-600 border border-orange-100">{t}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Collapsible filter panel - at bottom */}
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="w-full flex items-center justify-between px-5 py-3 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <span className="flex items-center gap-2">
              <Target className="w-4 h-4 text-slate-400" />
              筛选条件与重新匹配
            </span>
            <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
          </button>

          {showFilters && (
            <div className="px-5 pb-5 border-t border-slate-100 pt-4">
              <div className="grid md:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">个人资料</label>
                  <select
                    value={profileId}
                    onChange={e => setProfileId(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  >
                    <option value="">选择已有资料...</option>
                    {profiles.map(p => (
                      <option key={p.id} value={String(p.id)}>{p.nickname}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">专业方向（可选）</label>
                  <input
                    type="text" value={majorKeyword}
                    onChange={e => setMajorKeyword(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    placeholder="如：计算机、金融、法学..."
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">目标省份</label>
                  <select
                    value={targetProvince}
                    onChange={e => setTargetProvince(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  >
                    <option value="">不限</option>
                    {PROVINCES.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">目标层次</label>
                  <select
                    value={targetLevel}
                    onChange={e => setTargetLevel(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  >
                    <option value="">不限</option>
                    {SCHOOL_LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
                  </select>
                </div>
              </div>
              <button
                onClick={handleRecommend}
                disabled={loading || !profileId}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-700 text-white rounded-lg hover:bg-blue-800 disabled:opacity-60 disabled:cursor-not-allowed transition-colors font-medium text-sm"
              >
                {loading ? (
                  <><Loader2 className="w-4 h-4 animate-spin" />匹配中...</>
                ) : (
                  <><Target className="w-4 h-4" />重新匹配</>
                )}
              </button>
            </div>
          )}
        </div>
      </div>
    )
  }

  // ---- Empty / initial state ----
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">根据你的情况推荐以下院校</h1>
        <p className="text-slate-500">基于你的个人条件和偏好，推荐最适合的考研目标院校</p>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      {/* Filter panel - shown upfront when no results */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 mb-8">
        <h2 className="font-semibold text-slate-900 mb-5 flex items-center gap-2">
          <Target className="w-5 h-5 text-blue-700" />
          筛选条件
        </h2>

        <div className="grid md:grid-cols-2 gap-5 mb-5">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">个人资料</label>
            <select
              value={profileId}
              onChange={e => setProfileId(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
            >
              <option value="">选择已有资料...</option>
              {profiles.map(p => (
                <option key={p.id} value={String(p.id)}>{p.nickname}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">专业方向（可选）</label>
            <input
              type="text" value={majorKeyword}
              onChange={e => setMajorKeyword(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
              placeholder="如：计算机、金融、法学..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">目标省份</label>
            <select
              value={targetProvince}
              onChange={e => setTargetProvince(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
            >
              <option value="">不限</option>
              {PROVINCES.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">目标层次</label>
            <select
              value={targetLevel}
              onChange={e => setTargetLevel(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
            >
              <option value="">不限</option>
              {SCHOOL_LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </div>
        </div>

        <button
          onClick={handleRecommend}
          disabled={loading || !profileId}
          className="inline-flex items-center gap-2 px-6 py-2.5 bg-blue-700 text-white rounded-lg hover:bg-blue-800 disabled:opacity-60 disabled:cursor-not-allowed transition-colors font-medium text-sm"
        >
          {loading ? (
            <><Loader2 className="w-4 h-4 animate-spin" />匹配中...</>
          ) : (
            <><Target className="w-4 h-4" />开始院校匹配</>
          )}
        </button>
      </div>

      {/* Empty prompt */}
      <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
        <Target className="w-16 h-16 mx-auto mb-4 text-slate-300" />
        <h3 className="text-lg font-semibold text-slate-700 mb-2">开始院校匹配</h3>
        <p className="text-slate-500 max-w-md mx-auto">
          选择你的个人资料，设置目标省份和层次偏好，系统将综合分析为你匹配最合适的院校。
        </p>
      </div>
    </div>
  )
}

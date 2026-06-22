import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Loader2, AlertCircle, TrendingUp, TrendingDown, Minus,
  ChevronLeft, School, BookOpen, Target,
} from 'lucide-react'
import { api } from '../api/client'
import type { ScoreHistory, ScoreLine } from '../types'
import ScoreChart from '../components/ScoreChart'

const LEVEL_COLORS: Record<string, string> = {
  C9: 'bg-amber-50 text-amber-700 border-amber-200',
  '985': 'bg-red-50 text-red-700 border-red-200',
  '211': 'bg-blue-50 text-blue-700 border-blue-200',
  '军事院校': 'bg-green-50 text-green-700 border-green-200',
  '中外合作': 'bg-indigo-50 text-indigo-700 border-indigo-200',
  '双一流': 'bg-emerald-50 text-emerald-700 border-emerald-200',
  '普本': 'bg-slate-50 text-slate-600 border-slate-200',
}

export default function ScoreLineDetail() {
  const { schoolId, majorCode } = useParams<{ schoolId: string; majorCode: string }>()
  const navigate = useNavigate()

  const [data, setData] = useState<ScoreHistory | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeCategory, setActiveCategory] = useState<string>('all')

  useEffect(() => {
    if (!schoolId || !majorCode) return
    setLoading(true)
    setError(null)
    api.scoreLines.history(Number(schoolId), majorCode)
      .then(res => {
        if (res.success && res.data) {
          setData(res.data)
        } else {
          setError(res.error || '加载失败')
        }
        setLoading(false)
      })
      .catch(() => {
        setError('网络请求失败')
        setLoading(false)
      })
  }, [schoolId, majorCode])

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center text-slate-400">
        <Loader2 className="w-8 h-8 mx-auto mb-3 animate-spin" />
        加载分数线数据...
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 mb-6"
        >
          <ChevronLeft className="w-4 h-4" />返回
        </button>
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error || '数据不存在'}
        </div>
      </div>
    )
  }

  const allLines = data.score_lines
  const hasLines = allLines.length > 0

  // Get categories
  const categories = [...new Set(allLines.map(sl => sl.category))].sort()
  const filteredLines = activeCategory === 'all'
    ? allLines
    : allLines.filter(sl => sl.category === activeCategory)

  // Group by year for table
  const yearGroups = new Map<number, ScoreLine[]>()
  for (const sl of filteredLines) {
    const group = yearGroups.get(sl.year) || []
    group.push(sl)
    yearGroups.set(sl.year, group)
  }
  const sortedYears = [...yearGroups.keys()].sort((a, b) => b - a)

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Back button + Header */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 mb-4"
      >
        <ChevronLeft className="w-4 h-4" />返回招生分析
      </button>

      <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap mb-2">
              <h1 className="text-xl font-bold text-slate-900">{data.school_name}</h1>
              <span className={`text-xs px-2 py-0.5 rounded border ${LEVEL_COLORS[data.school_level] || 'bg-slate-50 text-slate-600 border-slate-200'}`}>
                {data.school_level}
              </span>
              <span className="text-xs text-slate-500">{data.school_province}</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <BookOpen className="w-4 h-4" />
              <span className="font-medium">{data.major_name || data.major_code}</span>
              <code className="text-xs bg-slate-100 px-1.5 py-0.5 rounded text-slate-500">{data.major_code}</code>
            </div>
          </div>
          {/* Score line count badge */}
          {hasLines && (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <div className="bg-blue-50 text-blue-700 px-3 py-1.5 rounded-lg text-sm font-medium">
                {allLines.length} 条分数线记录
              </div>
            </div>
          )}
        </div>
      </div>

      {!hasLines ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-400">
          <AlertCircle className="w-12 h-12 mx-auto mb-3 text-slate-300" />
          <p>{data.trend_analysis}</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Prediction Card */}
          {data.prediction && (
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-200 p-5">
              <div className="flex items-center gap-2 mb-3">
                <Target className="w-5 h-5 text-blue-700" />
                <h2 className="font-bold text-blue-900">{data.prediction.year}年分数线预测</h2>
                {data.prediction.direction === '上升' ? (
                  <TrendingUp className="w-4 h-4 text-red-500" />
                ) : data.prediction.direction === '下降' ? (
                  <TrendingDown className="w-4 h-4 text-green-500" />
                ) : (
                  <Minus className="w-4 h-4 text-slate-400" />
                )}
                <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                  data.prediction.direction === '上升' ? 'bg-red-100 text-red-700' :
                  data.prediction.direction === '下降' ? 'bg-green-100 text-green-700' :
                  'bg-slate-100 text-slate-600'
                }`}>
                  近5年总体{data.prediction.direction} ({data.prediction.annual_change > 0 ? '+' : ''}{data.prediction.annual_change}分)
                </span>
              </div>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-3xl font-bold text-blue-700">{data.prediction.predicted_score}</div>
                  <div className="text-xs text-blue-500 mt-1">预测总分</div>
                </div>
                <div>
                  <div className="text-lg font-semibold text-slate-600">{data.prediction.confidence_low} - {data.prediction.confidence_high}</div>
                  <div className="text-xs text-slate-400 mt-1">置信区间 (±{data.prediction.confidence_range}分)</div>
                </div>
                <div className="flex items-center justify-center">
                  <div className={`text-sm font-medium px-3 py-1 rounded-lg ${
                    data.prediction.direction === '上升' ? 'bg-red-50 text-red-600' :
                    data.prediction.direction === '下降' ? 'bg-green-50 text-green-600' :
                    'bg-slate-50 text-slate-500'
                  }`}>
                    预测趋势：{data.prediction.direction}
                  </div>
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-3">
                基于历年数据趋势预测，仅供参考。
              </p>
            </div>
          )}

          {/* Chart */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-blue-600" />
              历史分数线趋势
            </h2>
            <ScoreChart data={allLines} />
          </div>

          {/* Category filter */}
          {categories.length > 1 && (
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setActiveCategory('all')}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  activeCategory === 'all'
                    ? 'bg-blue-100 text-blue-700 border border-blue-200'
                    : 'bg-white text-slate-500 border border-slate-200'
                }`}
              >
                全部 ({allLines.length})
              </button>
              {categories.map(cat => {
                const count = allLines.filter(sl => sl.category === cat).length
                return (
                  <button
                    key={cat}
                    onClick={() => setActiveCategory(cat)}
                    className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                      activeCategory === cat
                        ? 'bg-blue-100 text-blue-700 border border-blue-200'
                        : 'bg-white text-slate-500 border border-slate-200'
                    }`}
                  >
                    {cat} ({count})
                  </button>
                )
              })}
            </div>
          )}

          {/* Score Table by Year */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100">
              <h2 className="font-bold text-slate-900">历年分数线明细</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 text-left">
                    <th className="px-4 py-2.5 font-medium text-slate-600">年份</th>
                    <th className="px-4 py-2.5 font-medium text-slate-600">类型</th>
                    <th className="px-4 py-2.5 font-medium text-slate-600 text-right">总分</th>
                    <th className="px-4 py-2.5 font-medium text-slate-600 text-right">政治</th>
                    <th className="px-4 py-2.5 font-medium text-slate-600 text-right">英语</th>
                    <th className="px-4 py-2.5 font-medium text-slate-600 text-right">业务课1</th>
                    <th className="px-4 py-2.5 font-medium text-slate-600 text-right">业务课2</th>
                    <th className="px-4 py-2.5 font-medium text-slate-600 text-right">复试总分</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedYears.map(year => {
                    const lines = yearGroups.get(year)!
                    return lines.map((sl, idx) => (
                      <tr key={`${year}-${idx}`} className="border-t border-slate-50 hover:bg-slate-50/50">
                        {idx === 0 && (
                          <td className="px-4 py-2.5 font-medium text-slate-900" rowSpan={lines.length}>
                            {sl.year}
                          </td>
                        )}
                        <td className="px-4 py-2.5">
                          <span className={`text-xs px-1.5 py-0.5 rounded ${
                            sl.category === '学硕' ? 'bg-purple-50 text-purple-700' : 'bg-teal-50 text-teal-700'
                          }`}>
                            {sl.category}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono font-semibold text-slate-900">
                          {sl.total_score}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-slate-500">
                          {sl.politics_score ?? '-'}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-slate-500">
                          {sl.english_score ?? '-'}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-slate-500">
                          {sl.business_score_1 ?? '-'}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-slate-500">
                          {sl.business_score_2 ?? '-'}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-slate-500">
                          {sl.re_exam_total_score ?? '-'}
                        </td>
                      </tr>
                    ))
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Trend Analysis Text */}
          <div className="bg-slate-50 rounded-xl border border-slate-200 p-5">
            <h2 className="font-bold text-slate-900 mb-2 flex items-center gap-2">
              <School className="w-5 h-5 text-indigo-600" />
              趋势分析
            </h2>
            <p className="text-sm text-slate-600 leading-relaxed">{data.trend_analysis}</p>
          </div>
        </div>
      )}
    </div>
  )
}

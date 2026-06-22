import { useState } from 'react'
import {
  ChevronDown, MapPin, TrendingUp, Users,
  AlertTriangle, ShieldCheck, ThumbsUp,
  GraduationCap, Target,
} from 'lucide-react'
import type { Recommendation } from '../types'

const TIER_STYLES: Record<string, { border: string; bg: string; badge: string; icon: typeof ShieldCheck }> = {
  '冲刺': { border: 'border-l-orange-500', bg: 'bg-orange-50', badge: 'text-orange-700 bg-orange-50 border-orange-200', icon: AlertTriangle },
  '稳妥': { border: 'border-l-emerald-500', bg: 'bg-emerald-50', badge: 'text-emerald-700 bg-emerald-50 border-emerald-200', icon: ShieldCheck },
  '保底': { border: 'border-l-blue-500', bg: 'bg-blue-50', badge: 'text-blue-700 bg-blue-50 border-blue-200', icon: ThumbsUp },
}

const MATCH_COLORS: Record<string, string> = {
  '冲刺': 'bg-orange-500',
  '稳妥': 'bg-emerald-500',
  '保底': 'bg-blue-500',
}

interface Props {
  rec: Recommendation
  index?: number
  analysis?: string
}

export default function RecommendationCard({ rec, index = 0 }: Props) {
  const [expanded, setExpanded] = useState(false)
  const tier = TIER_STYLES[rec.risk_level] || TIER_STYLES['稳妥']
  const TierIcon = tier.icon
  const matchColor = MATCH_COLORS[rec.risk_level] || 'bg-emerald-500'

  const levelBadges = rec.school_level
    .split(/[,，、]/)
    .map(s => s.trim())
    .filter(Boolean)

  return (
    <div className={`bg-white rounded-lg border border-slate-200 border-l-4 ${tier.border} overflow-hidden`}>
      {/* Main card body - always visible */}
      <div className="p-4">
        {/* Row 1: School name + risk badge + ranking */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 flex-wrap min-w-0">
            <h3 className="font-bold text-slate-900 text-base truncate">{rec.school_name}</h3>
            <span className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full border ${tier.badge}`}>
              {rec.risk_level}
            </span>
            {rec.is_research_institute && (
              <span className="shrink-0 text-xs px-1.5 py-0.5 rounded bg-purple-50 border border-purple-200 text-purple-700">
                研究院
              </span>
            )}
          </div>
          {rec.ranking_national && (
            <span className="shrink-0 text-xs text-slate-400">全国第{rec.ranking_national}名</span>
          )}
        </div>

        {/* Row 2: Level badges + school type + province */}
        <div className="flex items-center gap-1.5 flex-wrap mb-2">
          {levelBadges.map(b => (
            <span key={b} className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-medium">{b}</span>
          ))}
          {rec.school_type && (
            <span className="text-xs text-slate-400">{rec.school_type}类</span>
          )}
          <span className="text-xs text-slate-400">·</span>
          <span className="text-xs text-slate-400 flex items-center gap-0.5">
            <MapPin className="w-3 h-3" />{rec.school_province}
          </span>
        </div>

        {/* Row 3: Major name + code */}
        <div className="flex items-center gap-2 mb-3">
          <span className="text-sm font-medium text-slate-800">{rec.major_name}</span>
          {rec.major_code && (
            <code className="text-xs px-1 py-0.5 bg-slate-100 rounded text-slate-500 font-mono">{rec.major_code}</code>
          )}
          {rec.major_strength_label && rec.major_strength_label !== '学科数据不足' && (
            <span className={`text-xs px-1.5 py-0.5 rounded-full border ${
              rec.major_strength_score >= 85 ? 'bg-red-50 border-red-200 text-red-700' :
              rec.major_strength_score >= 70 ? 'bg-amber-50 border-amber-200 text-amber-700' :
              'bg-slate-100 border-slate-200 text-slate-600'
            }`}>
              {rec.major_strength_label}
            </span>
          )}
        </div>

        {/* Row 4: Match score bar + key metrics */}
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2 min-w-[140px]">
            <div className="flex-1 bg-slate-100 rounded-full h-2">
              <div
                className={`h-2 rounded-full ${matchColor}`}
                style={{ width: `${rec.match_score}%` }}
              />
            </div>
            <span className="text-sm font-bold text-slate-700 w-10 text-right">{rec.match_score}%</span>
            <span className="text-xs text-slate-400">推荐度</span>
          </div>

          {rec.planned_enrollment !== undefined && rec.planned_enrollment !== null && (
            rec.planned_enrollment > 0 ? (
              <span className="text-xs text-slate-500 flex items-center gap-1">
                <Users className="w-3 h-3" />招生 {rec.planned_enrollment} 人
              </span>
            ) : (
              <span className="text-xs text-red-600 font-medium flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />今年不招生
              </span>
            )
          )}

          {rec.re_exam_avg_score > 0 && (
            <span className="text-xs text-slate-500 flex items-center gap-1">
              <Target className="w-3 h-3" />复试均分 {rec.re_exam_avg_score}
            </span>
          )}

          {rec.department && (
            <span className="text-xs text-slate-400 truncate max-w-[200px]">{rec.department}</span>
          )}
        </div>

        {/* Row 5: Pros/Cons tags */}
        <div className="flex flex-wrap items-center gap-1.5 mt-3">
          {rec.pros.slice(0, 3).map((p, i) => (
            <span key={`pro-${i}`} className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100">
              + {p}
            </span>
          ))}
          {rec.cons.slice(0, 2).map((c, i) => (
            <span key={`con-${i}`} className="text-xs px-2 py-0.5 rounded-full bg-orange-50 text-orange-600 border border-orange-100">
              - {c}
            </span>
          ))}
          {(rec.pros.length > 0 || rec.cons.length > 0 || rec.score_trend) && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-0.5 ml-auto cursor-pointer"
            >
              {expanded ? '收起' : '查看分析'}
              <ChevronDown className={`w-3 h-3 transition-transform ${expanded ? 'rotate-180' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* Expanded detail section */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-100 pt-3 space-y-3">
          {rec.score_trend && (
            <div>
              <h5 className="text-xs font-semibold text-slate-500 mb-1 flex items-center gap-1">
                <TrendingUp className="w-3 h-3" />分数趋势
              </h5>
              <p className="text-xs text-slate-600 leading-relaxed">{rec.score_trend}</p>
            </div>
          )}

          {rec.competition && (
            <div>
              <h5 className="text-xs font-semibold text-slate-500 mb-1">竞争分析</h5>
              <p className="text-xs text-slate-600 leading-relaxed">{rec.competition}</p>
            </div>
          )}

          {rec.school_description && (
            <div>
              <h5 className="text-xs font-semibold text-slate-500 mb-1 flex items-center gap-1">
                <GraduationCap className="w-3 h-3" />学校概况
              </h5>
              <p className="text-xs text-slate-500 leading-relaxed">{rec.school_description}</p>
            </div>
          )}

          {rec.exam_subjects && rec.exam_subjects.length > 0 && (
            <div>
              <h5 className="text-xs font-semibold text-slate-500 mb-1">考试科目</h5>
              <div className="flex flex-wrap gap-1">
                {rec.exam_subjects.map((s, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 bg-indigo-50 border border-indigo-100 rounded text-indigo-700">{s}</span>
                ))}
              </div>
            </div>
          )}

          {rec.subject_warnings && rec.subject_warnings.length > 0 && (
            <div>
              <h5 className="text-xs font-semibold text-orange-600 mb-1 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />科目提醒
              </h5>
              {rec.subject_warnings.map((w, i) => (
                <p key={i} className="text-xs text-orange-600">{w}</p>
              ))}
            </div>
          )}

          {rec.pros.length > 0 && (
            <div>
              <h5 className="text-xs font-semibold text-slate-500 mb-1">全部优势</h5>
              <div className="flex flex-wrap gap-1">
                {rec.pros.map((p, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-100">+ {p}</span>
                ))}
              </div>
            </div>
          )}

          {rec.cons.length > 0 && (
            <div>
              <h5 className="text-xs font-semibold text-slate-500 mb-1">全部风险</h5>
              <div className="flex flex-wrap gap-1">
                {rec.cons.map((c, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 rounded bg-orange-50 text-orange-600 border border-orange-100">- {c}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

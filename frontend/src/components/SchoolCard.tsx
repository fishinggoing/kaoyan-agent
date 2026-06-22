import { MapPin, ExternalLink, Award, AlertTriangle } from 'lucide-react'
import type { School } from '../types'

const levelColors: Record<string, string> = {
  C9: 'bg-amber-50 text-amber-700 border-amber-200',
  '985': 'bg-red-50 text-red-700 border-red-200',
  '211': 'bg-blue-50 text-blue-700 border-blue-200',
  '军事院校': 'bg-green-50 text-green-700 border-green-200',
  '中外合作': 'bg-indigo-50 text-indigo-700 border-indigo-200',
  '双一流': 'bg-emerald-50 text-emerald-700 border-emerald-200',
  '普本': 'bg-slate-50 text-slate-600 border-slate-200',
}

const categoryLabels: Record<string, string> = {
  '成人本科': '成人本科',
  '专升本高校': '专升本高校',
}

const isGradExam = (category: string | null | undefined) =>
  !category || category === '考研高校'

export default function SchoolCard({ school }: { school: School }) {
  const isGrad = isGradExam(school.category)

  return (
    <div className={`bg-white rounded-xl border p-5 hover:shadow-md transition-all group ${isGrad ? 'border-slate-200 hover:border-blue-200' : 'border-amber-300 bg-amber-50/30'}`}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-slate-900 group-hover:text-blue-700 transition-colors">{school.name}</h3>
          <p className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
            <MapPin className="w-3 h-3" />{school.province} · {school.city}
          </p>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${levelColors[school.level] || levelColors['普本']}`}>
          {school.level}
        </span>
      </div>

      {/* Non-考研高校 warning tag */}
      {!isGrad && school.category && (
        <div className="flex items-center gap-1.5 mb-2 px-2 py-1 bg-amber-100 border border-amber-300 rounded-md text-xs font-medium text-amber-800">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          非考研高校 · {categoryLabels[school.category] || school.category}
        </div>
      )}

      {isGrad && (
        <div className="flex items-center gap-3 text-xs text-slate-500 mb-3">
          <span className="flex items-center gap-1">
            <Award className="w-3 h-3" />{school.school_type}
          </span>
          {school.is_graduate_school && (
            <span className="text-emerald-600 font-medium">研究生院</span>
          )}
        </div>
      )}

      {school.description && (
        <p className="text-xs text-slate-500 leading-relaxed line-clamp-2 mb-3">{school.description}</p>
      )}

      <div className="flex items-center justify-between">
        {school.ranking_national && (
          <span className="text-xs text-slate-400">全国排名 #{school.ranking_national}</span>
        )}
        {school.website && (
          <a
            href={school.website}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 no-underline"
          >
            <ExternalLink className="w-3 h-3" />官网
          </a>
        )}
      </div>
    </div>
  )
}

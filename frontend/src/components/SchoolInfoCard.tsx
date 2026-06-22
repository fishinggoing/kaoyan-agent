import { useState } from 'react'
import { ChevronDown, MapPin, GraduationCap, BookOpen, Trophy } from 'lucide-react'
import type { SchoolInfo } from '../types'

interface Props {
  school: SchoolInfo
}

export default function SchoolInfoCard({ school }: Props) {
  const [expanded, setExpanded] = useState(false)

  const levelBadges: string[] = []
  if (school.is_985) levelBadges.push('985')
  if (school.is_211) levelBadges.push('211')
  if (school.is_double_first) levelBadges.push('双一流')
  if (levelBadges.length === 0 && school.school_level) {
    levelBadges.push(school.school_level)
  }

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      <div className="p-4">
        {/* Row 1: School name + ranking */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <h3 className="font-bold text-slate-900 text-base">{school.school_name}</h3>
          {school.ranking_national && (
            <span className="shrink-0 text-xs text-slate-400 flex items-center gap-1">
              <Trophy className="w-3 h-3" />全国第{school.ranking_national}名
            </span>
          )}
        </div>

        {/* Row 2: Level badges + school type + province */}
        <div className="flex items-center gap-1.5 flex-wrap mb-2">
          {levelBadges.map(b => (
            <span key={b} className="text-xs px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 font-medium border border-indigo-100">{b}</span>
          ))}
          {school.school_type && (
            <span className="text-xs text-slate-400">{school.school_type}类</span>
          )}
          <span className="text-xs text-slate-400">·</span>
          <span className="text-xs text-slate-400 flex items-center gap-0.5">
            <MapPin className="w-3 h-3" />{school.school_province}
          </span>
        </div>

        {/* Row 3: Description */}
        {school.school_description && (
          <p className="text-xs text-slate-500 leading-relaxed mb-2 line-clamp-2">
            {school.school_description}
          </p>
        )}

        {/* Row 4: Majors count + expand button */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 flex items-center gap-1">
            <BookOpen className="w-3 h-3" />
            {school.majors_count > 0
              ? `${school.majors_count} 个招生专业`
              : '暂无专业数据'}
          </span>
          {school.majors.length > 0 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-0.5 ml-auto cursor-pointer"
            >
              {expanded ? '收起' : '查看专业'}
              <ChevronDown className={`w-3 h-3 transition-transform ${expanded ? 'rotate-180' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* Expanded: Major list */}
      {expanded && school.majors.length > 0 && (
        <div className="px-4 pb-4 border-t border-slate-100 pt-3 space-y-2">
          {school.majors.map((m, i) => (
            <div key={`${m.major_code}-${i}`} className="flex items-start justify-between gap-2 py-1.5 border-b border-slate-50 last:border-0">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-800">{m.major_name}</span>
                  <code className="text-xs px-1 py-0.5 bg-slate-100 rounded text-slate-500 font-mono">{m.major_code}</code>
                </div>
                {m.department && (
                  <p className="text-xs text-slate-400 mt-0.5">{m.department}{m.direction ? ` · ${m.direction}` : ''}</p>
                )}
                {m.exam_subjects.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {m.exam_subjects.map((s, j) => (
                      <span key={j} className="text-[10px] px-1.5 py-0.5 bg-slate-50 border border-slate-100 rounded text-slate-500">{s}</span>
                    ))}
                  </div>
                )}
              </div>
              {m.planned_enrollment != null && m.planned_enrollment > 0 && (
                <span className="shrink-0 text-xs text-slate-400">招{m.planned_enrollment}人</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

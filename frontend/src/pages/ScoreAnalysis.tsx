import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart3, AlertCircle, Loader2, BookOpen, Users, School as SchoolIcon, TrendingUp } from 'lucide-react'
import { api } from '../api/client'
import type { School, SchoolMajor } from '../types'
import SearchableSelect from '../components/SearchableSelect'

interface EnrollmentSummary {
  school_id: number
  total_majors: number
  total_planned_enrollment: number
  total_push_free: number
  majors_not_enrolling: number
  majors_enrolling: number
}

export default function ScoreAnalysis() {
  const navigate = useNavigate()
  const [selectedSchool, setSelectedSchool] = useState<School | null>(null)
  const [schoolMajors, setSchoolMajors] = useState<SchoolMajor[]>([])
  const [enrollmentSummary, setEnrollmentSummary] = useState<EnrollmentSummary | null>(null)

  const [schoolOptions, setSchoolOptions] = useState<School[]>([])
  const [loadingSchools, setLoadingSchools] = useState(false)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showNotEnrolling, setShowNotEnrolling] = useState(false)

  const hasFocusedSchool = useRef(false)

  const handleSchoolSearch = useCallback((query: string) => {
    if (!query.trim()) {
      setLoadingSchools(true)
      api.schools.list({ size: 100, page: 1 }).then(res => {
        if (res.success && res.data) setSchoolOptions(res.data.items)
        else setSchoolOptions([])
        setLoadingSchools(false)
      }).catch(() => { setSchoolOptions([]); setLoadingSchools(false) })
      return
    }
    setLoadingSchools(true)
    api.schools.search(query, 1, 50).then(res => {
      if (res.success && res.data) setSchoolOptions(res.data.items)
      else setSchoolOptions([])
      setLoadingSchools(false)
    }).catch(() => { setSchoolOptions([]); setLoadingSchools(false) })
  }, [])

  const handleSchoolFocus = useCallback(() => {
    if (hasFocusedSchool.current) return
    hasFocusedSchool.current = true
    setLoadingSchools(true)
    api.schools.list({ size: 100, page: 1 }).then(res => {
      if (res.success && res.data) setSchoolOptions(res.data.items)
      setLoadingSchools(false)
    }).catch(() => { setLoadingSchools(false) })
  }, [])

  useEffect(() => {
    if (!selectedSchool) {
      setSchoolMajors([])
      setEnrollmentSummary(null)
      setSchoolOptions([])
      hasFocusedSchool.current = false
      return
    }
    hasFocusedSchool.current = false
    setLoading(true)
    setError(null)
    Promise.all([
      api.majors.bySchool(selectedSchool.id, { size: 500 }),
      api.scoreLines.schoolSummary(selectedSchool.id),
    ]).then(([mRes, sRes]) => {
      if (mRes.success && mRes.data) setSchoolMajors(mRes.data.items)
      else { setSchoolMajors([]); setError(mRes.error || '加载失败') }
      if (sRes.success && sRes.data) setEnrollmentSummary(sRes.data)
      setLoading(false)
    }).catch((err) => {
      console.error('Failed to load enrollment data:', err)
      setError('网络请求失败')
      setLoading(false)
    })
  }, [selectedSchool])

  const withoutEnrollment = useMemo(() => schoolMajors.filter(sm => (sm.planned_enrollment || 0) === 0), [schoolMajors])
  const displayedMajors = showNotEnrolling ? withoutEnrollment : schoolMajors

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">招生信息查询</h1>
        <p className="text-slate-500">查看院校各专业拟招收人数、推免人数与考试科目</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6">
        <div className="flex flex-wrap gap-3 items-end">
          <div className="min-w-56 flex-1">
            <label className="block text-xs font-medium text-slate-500 mb-1">院校</label>
            <SearchableSelect<School>
              value={selectedSchool}
              options={schoolOptions}
              onChange={setSelectedSchool}
              onSearch={handleSchoolSearch}
              onFocus={handleSchoolFocus}
              loading={loadingSchools}
              placeholder="输入院校名称搜索..."
              emptyText="未找到匹配院校"
              renderLabel={s => s.name}
              renderSublabel={s => `${s.province || ''} · ${s.level}`}
              getKey={s => s.id}
            />
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700 mb-6 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-16 text-slate-400">
          <Loader2 className="w-8 h-8 mx-auto mb-3 animate-spin" />
          加载招生数据...
        </div>
      ) : selectedSchool && schoolMajors.length > 0 ? (
        <div className="space-y-6">
          {/* Enrollment Summary */}
          {enrollmentSummary && (
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                <div className="text-2xl font-bold text-blue-700">{enrollmentSummary.total_majors}</div>
                <div className="text-xs text-slate-500 mt-1">招生专业</div>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                <div className="text-2xl font-bold text-emerald-700">{enrollmentSummary.total_planned_enrollment}</div>
                <div className="text-xs text-slate-500 mt-1">拟招收总人数</div>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                <div className="text-2xl font-bold text-purple-700">{enrollmentSummary.total_push_free}</div>
                <div className="text-xs text-slate-500 mt-1">推免人数</div>
              </div>
            </div>
          )}

          {/* View toggle */}
          {withoutEnrollment.length > 0 && (
            <div className="flex gap-2">
              <button
                onClick={() => setShowNotEnrolling(false)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  !showNotEnrolling ? 'bg-blue-100 text-blue-700 border border-blue-200' : 'bg-white text-slate-500 border border-slate-200'
                }`}
              >
                全部专业 ({schoolMajors.length})
              </button>
              <button
                onClick={() => setShowNotEnrolling(true)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 ${
                  showNotEnrolling ? 'bg-amber-100 text-amber-700 border border-amber-200' : 'bg-white text-slate-500 border border-slate-200'
                }`}
              >
                招生人数待公布 ({withoutEnrollment.length})
              </button>
            </div>
          )}

          {/* Major list */}
          <div className="space-y-3">
            {displayedMajors.map(sm => {
              const noEnrollment = (sm.planned_enrollment || 0) === 0
              return (
                <div key={sm.id} className={`bg-white rounded-xl border p-5 ${noEnrollment ? 'border-amber-200 bg-amber-50/30' : 'border-slate-200'}`}>
                  <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-slate-900">{sm.major_name}</span>
                        <code className="text-xs bg-slate-100 px-1.5 py-0.5 rounded text-slate-500">{sm.major_code}</code>
                        <span className="text-xs bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">{sm.study_mode}</span>
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-xs text-slate-500">
                        {sm.department && <span className="inline-flex items-center gap-1"><SchoolIcon className="w-3 h-3" />{sm.department}</span>}
                        {sm.direction && sm.direction !== '不区分招生方向' && <span>方向: {sm.direction}</span>}
                        <span>{sm.major_category} · {sm.major_discipline} · {sm.degree_type}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      {noEnrollment ? (
                        <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-100 border border-amber-200 rounded-lg text-sm font-medium text-amber-700">
                          招生人数待公布
                        </span>
                      ) : (
                        <>
                          <div className="text-center">
                            <div className="text-lg font-bold text-emerald-700 flex items-center gap-1">
                              <Users className="w-4 h-4" />{sm.planned_enrollment}
                            </div>
                            <div className="text-[10px] text-slate-400">拟招收人数</div>
                          </div>
                          {(sm.push_free_count || 0) > 0 && (
                            <div className="text-center">
                              <div className="text-lg font-bold text-purple-700">{sm.push_free_count}</div>
                              <div className="text-[10px] text-slate-400">推免人数</div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    {/* 分数线趋势按钮 */}
                    <button
                      onClick={() => navigate(`/scores/${selectedSchool!.id}/${sm.major_code}`)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-lg text-sm font-medium text-blue-700 hover:bg-blue-100 transition-colors"
                    >
                      <TrendingUp className="w-4 h-4" />查看分数线
                    </button>
                  </div>

                  {/* Exam subjects */}
                  {(sm.exam_politics || sm.exam_english || sm.exam_math || (sm.exam_course1_name && sm.exam_course1_name !== '无')) && (
                    <div className="bg-slate-50 rounded-lg p-3 flex items-start gap-2">
                      <BookOpen className="w-4 h-4 text-indigo-500 mt-0.5 shrink-0" />
                      <div className="flex flex-wrap gap-1.5">
                        {sm.exam_politics && (
                          <span className="text-xs px-2 py-0.5 bg-red-50 border border-red-100 rounded text-red-600">{sm.exam_politics}</span>
                        )}
                        {sm.exam_english && (
                          <span className="text-xs px-2 py-0.5 bg-amber-50 border border-amber-100 rounded text-amber-600">{sm.exam_english}</span>
                        )}
                        {sm.exam_math && (
                          <span className="text-xs px-2 py-0.5 bg-blue-50 border border-blue-100 rounded text-blue-600">{sm.exam_math}</span>
                        )}
                        {sm.exam_course1_name && sm.exam_course1_name !== '无' && (
                          <span className="text-xs px-2 py-0.5 bg-purple-50 border border-purple-100 rounded text-purple-600">
                            {sm.exam_course1_code && sm.exam_course1_code !== '-' ? `${sm.exam_course1_code} ` : ''}{sm.exam_course1_name}
                          </span>
                        )}
                        {sm.exam_course2_name && sm.exam_course2_name !== '无' && (
                          <span className="text-xs px-2 py-0.5 bg-indigo-50 border border-indigo-100 rounded text-indigo-600">
                            {sm.exam_course2_code && sm.exam_course2_code !== '-' && sm.exam_course2_code !== '--' ? `${sm.exam_course2_code} ` : ''}{sm.exam_course2_name}
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {noEnrollment && (
                    <div className="mt-3 text-sm text-amber-600 font-medium flex items-center gap-1.5">
                      <AlertCircle className="w-4 h-4" />该专业招生人数暂未公布，可查看历史分数线了解招生情况
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ) : selectedSchool ? (
        <div className="text-center py-16 text-slate-400">
          <BarChart3 className="w-12 h-12 mx-auto mb-3 text-slate-300" />
          <p>该院校暂无招生专业数据</p>
        </div>
      ) : (
        <div className="text-center py-16 text-slate-400">
          <BarChart3 className="w-12 h-12 mx-auto mb-3 text-slate-300" />
          <p>选择院校查看各专业拟招收人数与考试科目</p>
        </div>
      )}
    </div>
  )
}

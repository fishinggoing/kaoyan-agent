import { useState, useEffect, useCallback } from 'react'
import { MapPin, Building2, GraduationCap, ChevronRight, ArrowLeft, Sparkles, Loader2, ThumbsUp, ThumbsDown, Target, AlertTriangle, Users, Ban } from 'lucide-react'
import { api } from '../api/client'
import type { SchoolOption, FilterOptions, AnalyzeResult, SchoolMajor } from '../types'
import SchoolCard from '../components/SchoolCard'

type Step = 'province' | 'level' | 'school' | 'major'

const LEVEL_LABELS: Record<string, string> = {
  C9: 'C9联盟',
  '985': '985工程',
  '211': '211工程',
  '双一流': '双一流',
  '普本': '普通本科',
}

const LEVEL_ORDER = ['C9', '985', '211', '双一流', '普本']

export default function SchoolSearch() {
  const [step, setStep] = useState<Step>('province')
  const [filters, setFilters] = useState<FilterOptions | null>(null)
  const [provinceLevelCounts, setProvinceLevelCounts] = useState<Record<string, number> | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingLevels, setLoadingLevels] = useState(false)

  // User selections
  const [selectedProvince, setSelectedProvince] = useState('')
  const [selectedLevel, setSelectedLevel] = useState('')
  const [selectedSchool, setSelectedSchool] = useState<SchoolOption | null>(null)

  // Results
  const [schools, setSchools] = useState<SchoolOption[]>([])
  const [schoolMajors, setSchoolMajors] = useState<SchoolMajor[]>([])

  // AI Analysis
  const [analyzing, setAnalyzing] = useState<number | null>(null)
  const [analyses, setAnalyses] = useState<Record<number, AnalyzeResult>>({})

  const analyzeMajor = useCallback(async (sm: SchoolMajor) => {
    setAnalyzing(sm.id)
    const res = await api.decisions.analyze(selectedSchool!.id, sm.major_code, undefined)
    if (res.success && res.data) {
      setAnalyses(prev => ({ ...prev, [sm.id]: res.data! }))
    }
    setAnalyzing(null)
  }, [selectedSchool])

  useEffect(() => {
    api.schools.filters().then(res => {
      if (res.success && res.data) setFilters(res.data)
    })
  }, [])

  const selectProvince = async (province: string) => {
    setSelectedProvince(province)
    setStep('level')
    // Fetch schools in this province to compute level counts
    setLoadingLevels(true)
    const res = await api.schools.list({ province, size: 500 })
    if (res.success && res.data) {
      const raw: Record<string, number> = {}
      for (const s of res.data.items) {
        const lv = s.level
        if (lv) raw[lv] = (raw[lv] || 0) + 1
      }
      const counts: Record<string, number> = {}
      const tiers: [string, string[]][] = [
        ['C9', ['C9']],
        ['985', ['C9', '985']],
        ['211', ['C9', '985', '211']],
        ['双一流', ['C9', '985', '211', '双一流']],
        ['普本', ['普本']],
      ]
      for (const [label, included] of tiers) {
        const total = included.reduce((sum, lv) => sum + (raw[lv] || 0), 0)
        if (total > 0) counts[label] = total
      }
      setProvinceLevelCounts(counts)
    }
    setLoadingLevels(false)
  }

  const selectLevel = useCallback(async (level: string) => {
    setSelectedLevel(level)
    setLoading(true)
    const res = await api.schools.options({ province: selectedProvince, level, limit: 200 })
    if (res.success && res.data) {
      setSchools(res.data.items)
    }
    setLoading(false)
    setStep('school')
  }, [selectedProvince])

  const selectSchool = useCallback(async (school: SchoolOption) => {
    setSelectedSchool(school)
    setLoading(true)
    const res = await api.majors.bySchool(school.id, { size: 500 })
    if (res.success && res.data) {
      setSchoolMajors(res.data.items)
    }
    setLoading(false)
    setStep('major')
  }, [])

  const resetTo = (target: Step) => {
    setStep(target)
    setAnalyses({})
    if (target === 'province') {
      setSelectedProvince(''); setSelectedLevel(''); setSelectedSchool(null)
      setSchools([]); setSchoolMajors([])
    } else if (target === 'level') {
      setSelectedLevel(''); setSelectedSchool(null)
      setSchools([]); setSchoolMajors([])
    }
  }

  const availableLevels = selectedProvince
    ? LEVEL_ORDER
    : LEVEL_ORDER

  // Use province-specific counts when available, otherwise national counts
  const levelCounts = provinceLevelCounts ?? filters?.levels

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-slate-500 mb-6">
        <button onClick={() => resetTo('province')} className="hover:text-blue-600">
          院校选择
        </button>
        {selectedProvince && (
          <>
            <ChevronRight className="w-4 h-4" />
            <button onClick={() => resetTo('level')} className="hover:text-blue-600">
              {selectedProvince}
            </button>
          </>
        )}
        {selectedLevel && (
          <>
            <ChevronRight className="w-4 h-4" />
            <span>{LEVEL_LABELS[selectedLevel] || selectedLevel}</span>
          </>
        )}
        {selectedSchool && (
          <>
            <ChevronRight className="w-4 h-4" />
            <span className="text-slate-800 font-medium">{selectedSchool.name}</span>
          </>
        )}
      </div>

      {/* Step 1: Select Province */}
      {step === 'province' && (
        <section>
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-slate-900 mb-2">选择目标省份</h1>
            <p className="text-slate-500">第一步：选择你想报考的省份</p>
          </div>
          {!filters ? (
            <div className="text-center py-16 text-slate-400">加载中...</div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
              {filters.provinces.map(({ province, count }) => (
                <button
                  key={province}
                  onClick={() => selectProvince(province)}
                  className="flex items-center gap-3 p-4 bg-white border border-slate-200 rounded-xl hover:border-blue-300 hover:shadow-sm transition-all text-left group"
                >
                  <MapPin className="w-5 h-5 text-slate-400 group-hover:text-blue-500 shrink-0" />
                  <div>
                    <div className="font-medium text-slate-800 group-hover:text-blue-700">{province}</div>
                    <div className="text-xs text-slate-400">{count}所</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Step 2: Select Level */}
      {step === 'level' && (
        <section>
          <button
            onClick={() => resetTo('province')}
            className="flex items-center gap-1 text-sm text-slate-500 hover:text-blue-600 mb-4"
          >
            <ArrowLeft className="w-4 h-4" /> 返回省份选择
          </button>
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-slate-900 mb-2">
              {selectedProvince} — 选择院校层次
            </h1>
            <p className="text-slate-500">第二步：选择目标院校层次</p>
          </div>
          {loadingLevels ? (
            <div className="text-center py-12 text-slate-400">计算中...</div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {availableLevels.map(level => {
                const count = levelCounts?.[level]
                return (
                  <button
                    key={level}
                    disabled={!count}
                    onClick={() => selectLevel(level)}
                    className="flex items-center justify-between p-4 bg-white border border-slate-200 rounded-xl hover:border-blue-300 hover:shadow-sm transition-all text-left disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <div className="flex items-center gap-3">
                      <Building2 className="w-5 h-5 text-slate-400" />
                      <span className="font-medium text-slate-800">{LEVEL_LABELS[level] || level}</span>
                    </div>
                    {count !== undefined && (
                      <span className="text-xs text-slate-400">{count}所</span>
                    )}
                  </button>
                )
              })}
            </div>
          )}
        </section>
      )}

      {/* Step 3: Select School */}
      {step === 'school' && (
        <section>
          <button
            onClick={() => resetTo('level')}
            className="flex items-center gap-1 text-sm text-slate-500 hover:text-blue-600 mb-4"
          >
            <ArrowLeft className="w-4 h-4" /> 返回层次选择
          </button>
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-slate-900 mb-2">
              {selectedProvince} · {LEVEL_LABELS[selectedLevel] || selectedLevel} — 选择院校
            </h1>
            <p className="text-slate-500">第三步：选择目标院校（共{loading ? '...' : schools.length}所）</p>
          </div>
          {loading ? (
            <div className="text-center py-16 text-slate-400">加载中...</div>
          ) : schools.length === 0 ? (
            <div className="text-center py-16 text-slate-400">
              <Building2 className="w-12 h-12 mx-auto mb-3 text-slate-300" />
              <p>该条件下暂无匹配院校</p>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {schools.map(school => (
                <button
                  key={school.id}
                  onClick={() => selectSchool(school)}
                  className="text-left"
                >
                  <SchoolCard school={school as unknown as import('../types').School} />
                </button>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Step 4: View School + Majors */}
      {step === 'major' && selectedSchool && (
        <section>
          <button
            onClick={() => resetTo('school')}
            className="flex items-center gap-1 text-sm text-slate-500 hover:text-blue-600 mb-4"
          >
            <ArrowLeft className="w-4 h-4" /> 返回院校列表
          </button>
          <div className="bg-white border border-slate-200 rounded-xl p-6 mb-6">
            <SchoolCard school={selectedSchool as unknown as import('../types').School} />
          </div>

          <div className="mb-6">
            <h2 className="text-xl font-bold text-slate-900 mb-1">
              <GraduationCap className="inline w-5 h-5 mr-2" />
              招生专业列表
            </h2>
            <p className="text-slate-500">该院校的研究生招生专业、拟招收人数与考试科目</p>
          </div>

          {loading ? (
            <div className="text-center py-8 text-slate-400">加载中...</div>
          ) : schoolMajors.length === 0 ? (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-6 text-center">
              <p className="text-amber-700 font-medium">该院校暂无招生专业数据</p>
              <p className="text-amber-600 text-sm mt-1">请尝试其他院校。</p>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 gap-3">
              {schoolMajors.map(sm => {
                const analysis = analyses[sm.id]
                const isAnalyzing = analyzing === sm.id
                const noEnrollment = sm.planned_enrollment === 0 || sm.planned_enrollment === null
                return (
                <div key={sm.id} className={`bg-white border rounded-lg p-4 transition-colors ${noEnrollment ? 'border-red-200 bg-red-50/30' : 'border-slate-200 hover:border-blue-300'}`}>
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex-1">
                      <div className="flex items-center flex-wrap gap-1.5">
                        <span className="font-medium text-slate-800">{sm.major_name}</span>
                        <span className="text-xs bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">{sm.major_code}</span>
                        <span className="text-xs bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">{sm.study_mode}</span>
                      </div>
                      {sm.department && (
                        <div className="text-xs text-slate-500 mt-1">院系: {sm.department}</div>
                      )}
                      {sm.direction && sm.direction !== '不区分招生方向' && (
                        <div className="text-xs text-slate-500">方向: {sm.direction}</div>
                      )}
                    </div>
                    <div className="shrink-0 ml-2 flex flex-col items-end gap-1.5">
                      {noEnrollment ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-red-700 bg-red-100 border border-red-200 rounded-full whitespace-nowrap">
                          <Ban className="w-3 h-3" />今年不招收
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full whitespace-nowrap">
                          <Users className="w-3 h-3" />拟招收 {sm.planned_enrollment} 人
                        </span>
                      )}
                      {!analysis && (
                        <button
                          onClick={() => analyzeMajor(sm)}
                          disabled={isAnalyzing}
                          className="shrink-0 inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-purple-600 bg-purple-50 border border-purple-200 rounded hover:bg-purple-100 disabled:opacity-50 transition-colors"
                        >
                          {isAnalyzing ? (
                            <><Loader2 className="w-3 h-3 animate-spin" />分析中</>
                          ) : (
                            <><Sparkles className="w-3 h-3" />AI 分析</>
                          )}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Exam subjects */}
                  {(sm.exam_politics || sm.exam_english || sm.exam_math || sm.exam_course1_name) && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {sm.exam_politics && (
                        <span className="text-xs px-1.5 py-0.5 bg-red-50 border border-red-100 rounded text-red-600">{sm.exam_politics}</span>
                      )}
                      {sm.exam_english && (
                        <span className="text-xs px-1.5 py-0.5 bg-amber-50 border border-amber-100 rounded text-amber-600">{sm.exam_english}</span>
                      )}
                      {sm.exam_math && (
                        <span className="text-xs px-1.5 py-0.5 bg-blue-50 border border-blue-100 rounded text-blue-600">{sm.exam_math}</span>
                      )}
                      {sm.exam_course1_name && sm.exam_course1_name !== '无' && (
                        <span className="text-xs px-1.5 py-0.5 bg-purple-50 border border-purple-100 rounded text-purple-600">
                          {sm.exam_course1_code && sm.exam_course1_code !== '-' ? `${sm.exam_course1_code} ` : ''}{sm.exam_course1_name}
                        </span>
                      )}
                      {sm.exam_course2_name && sm.exam_course2_name !== '无' && (
                        <span className="text-xs px-1.5 py-0.5 bg-indigo-50 border border-indigo-100 rounded text-indigo-600">
                          {sm.exam_course2_code && sm.exam_course2_code !== '-' && sm.exam_course2_code !== '--' ? `${sm.exam_course2_code} ` : ''}{sm.exam_course2_name}
                        </span>
                      )}
                    </div>
                  )}

                  <div className="text-xs text-slate-500 mt-2 space-y-0.5">
                    <div>学科门类: {sm.major_category} · {sm.major_discipline}</div>
                    <div>学位类型: {sm.degree_type}</div>
                    {noEnrollment && (
                      <div className="text-red-600 font-medium flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />重点注意：该专业今年不招收研究生
                      </div>
                    )}
                  </div>

                  {analysis && (
                    <div className="mt-3 border-t pt-3 border-purple-100">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                          analysis.risk_level === '冲刺' ? 'bg-orange-100 text-orange-700' :
                          analysis.risk_level === '保底' ? 'bg-blue-100 text-blue-700' :
                          'bg-emerald-100 text-emerald-700'
                        }`}>{analysis.risk_level}</span>
                        <span className="text-xs text-slate-400">推荐度 {analysis.match_score}%</span>
                      </div>
                      <p className="text-xs text-slate-600 mb-2">{analysis.analysis}</p>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <span className="text-emerald-600 font-medium">优势</span>
                          <ul className="mt-0.5 space-y-0.5">
                            {analysis.pros.map((p, i) => (
                              <li key={i} className="text-slate-500 flex items-start gap-1">
                                <ThumbsUp className="w-3 h-3 text-emerald-400 mt-0.5 shrink-0" />{p}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <span className="text-orange-600 font-medium">劣势</span>
                          <ul className="mt-0.5 space-y-0.5">
                            {analysis.cons.map((c, i) => (
                              <li key={i} className="text-slate-500 flex items-start gap-1">
                                <ThumbsDown className="w-3 h-3 text-orange-400 mt-0.5 shrink-0" />{c}
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                      {analysis.preparation_tips && (
                        <div className="mt-2 text-xs text-slate-500 flex items-start gap-1">
                          <Target className="w-3 h-3 text-amber-500 mt-0.5 shrink-0" />
                          {analysis.preparation_tips}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                )
              })}
            </div>
          )}
        </section>
      )}
    </div>
  )
}

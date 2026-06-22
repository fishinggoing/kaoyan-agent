export interface ApiResponse<T> {
  success: boolean
  data: T | null
  error: string | null
}

export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface SchoolOption {
  id: number
  name: string
  province: string
  city: string
  level: SchoolLevel
  category: SchoolCategory | null
  school_type: SchoolType
  ranking_national: number | null
}

export interface FilterOptions {
  provinces: { province: string; count: number }[]
  levels: Record<string, number>
}

export interface School {
  id: number
  name: string
  province: string | null
  city: string | null
  level: SchoolLevel
  category: SchoolCategory | null
  school_type: SchoolType | null
  is_985: boolean
  is_211: boolean
  is_double_first: boolean
  is_graduate_school: boolean
  website: string | null
  description: string | null
  ranking_national: number | null
  graduate_school_url: string | null
}

export type SchoolLevel = 'C9' | '985' | '211' | '双一流' | '军事院校' | '中外合作' | '普本'
export type SchoolCategory = '成人本科' | '专升本高校' | '考研高校'
export type SchoolType = '综合' | '理工' | '师范' | '财经' | '农林' | '医药' | '文法' | '艺体' | '军事' | '科研'

export interface Major {
  id: number
  code: string
  name: string
  category: string | null
  discipline: string | null
  degree_type: string | null
  school_count?: number
}

export interface SchoolMajor {
  id: number
  school_id: number
  school_name?: string
  school_level?: string
  school_province?: string | null
  major_id: number
  major_code: string
  major_name: string
  major_category?: string | null
  major_discipline?: string | null
  degree_type?: string | null
  department: string | null
  direction: string | null
  study_mode: string | null
  planned_enrollment: number | null
  push_free_count: number | null
  year: number | null
  exam_politics: string | null
  exam_english: string | null
  exam_math: string | null
  exam_course1_name: string | null
  exam_course1_code: string | null
  exam_course2_name: string | null
  exam_course2_code: string | null
  exam_course3_name: string | null
  exam_course3_code: string | null
}

export interface ScoreLine {
  id: number
  school_id: number
  school_name?: string
  major_code: string
  major_name?: string
  year: number
  category: string
  total_score: number
  politics_score: number | null
  english_score: number | null
  business_score_1: number | null
  business_score_2: number | null
  applicant_count: number | null
  admit_count: number | null
  is_national_line: boolean
  re_exam_total_score: number | null
  re_exam_politics_score: number | null
  re_exam_english_score: number | null
  re_exam_business_score_1: number | null
  re_exam_business_score_2: number | null
}

export interface ScoreTrend {
  school_id: number
  school_name: string
  major_code: string
  major_name: string
  data_points: ScoreLine[]
  trend_analysis: string
}

export interface ScorePrediction {
  year: number
  predicted_score: number
  confidence_low: number
  confidence_high: number
  direction: string
  annual_change: number
  confidence_range: number
}

export interface ScoreHistory {
  school_id: number
  school_name: string
  school_level: string
  school_province: string
  major_code: string
  major_name: string
  score_lines: ScoreLine[]
  trend_analysis: string
  prediction: ScorePrediction | null
}

export interface UserProfile {
  id: number
  nickname: string
  undergraduate_school: string | null
  undergraduate_major: string | null
  target_province: string | null
  target_level: string | null
  estimated_score: number | null
  available_hours_per_day: number | null
  exam_year: number | null
  notes: string | null
  exam_config: ExamConfig
  subject_strengths: Record<string, string>
  preference_weights?: PreferenceWeights | null
}

export interface ExamConfig {
  math?: string
  english?: string
  politics?: string
  专业课?: string
}

export interface PlanPhase {
  name: string
  weeks: number
  focus: string
  subjects: Record<string, string>
  tasks: string[]
  weekly_hours: number
  checkpoint: string
}

export interface DailySchedule {
  weekday: { time: string; subject: string; task: string }[]
  weekend: { time: string; subject: string; task: string }[]
}

export interface Material {
  subject: string
  books: string[]
}

export interface Recommendation {
  school_name: string
  school_province: string
  school_level: string
  school_type: string
  school_description: string
  ranking_national: number | null
  major_name: string
  major_code: string
  risk_level: '冲刺' | '稳妥' | '保底'
  match_score: number
  score_trend: string
  competition: string
  re_exam_avg_score: number
  pros: string[]
  cons: string[]
  exam_subjects: string[]
  subject_warnings: string[]
  major_match_level: string
  major_strength_score: number
  major_strength_label: string
  is_research_institute: boolean
  planned_enrollment?: number | null
  department?: string | null
  direction?: string | null
  study_mode?: string | null
}

export interface DecisionResult {
  recommendations: Recommendation[]
  analysis: string
  plan_suggestion: string
}

export interface AnalyzeResult {
  risk_level: string
  match_score: number
  score_trend: string
  competition: string
  pros: string[]
  cons: string[]
  analysis: string
  preparation_tips: string
}

export interface ScoreCard {
  id: number
  school_name: string
  major_name: string
  major_code: string
  exam_subjects: string[]
  score_data: ScoreLine[]
  created_at: string | null
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface PreferenceWeights {
  province_priority: number
  level_priority: number
  major_priority: number
  score_priority: number
  major_strength_priority: number
  risk_tolerance: '保守' | '适中' | '激进'
  career_goal: string
  preferred_cities: string[]
  preferred_majors: string[]
  excluded_provinces: string[]
  reasoning: string
}

export interface IntentRecommendParams {
  target_province?: string
  provinces_mentioned?: string[]
  target_level?: string
  major_keyword?: string
  schools_mentioned?: string[]
}

export interface IntentPlanParams {
  target_school?: string
  target_major?: string
  target_province?: string
}

export interface IntentParams {
  recommend?: IntentRecommendParams
  plan?: IntentPlanParams
}

export interface NeedsChatResponse {
  reply: string
  weights: PreferenceWeights | null
  is_complete: boolean
  intents?: string[]
  intent_params?: IntentParams
  recommendation_preview?: RecommendationPreview | null
  school_cards?: SchoolInfo[] | null
}

export interface RecommendationPreview {
  recommendations: Recommendation[]
  analysis: string
  source_schools: string[]
}

export interface SchoolMajorInfo {
  major_name: string
  major_code: string
  department?: string | null
  direction?: string | null
  study_mode?: string | null
  planned_enrollment?: number | null
  exam_subjects: string[]
}

export interface SchoolInfo {
  school_name: string
  school_province: string
  school_level: string
  school_type: string
  school_description: string
  ranking_national: number | null
  is_985: boolean
  is_211: boolean
  is_double_first: boolean
  majors: SchoolMajorInfo[]
  majors_count: number
}


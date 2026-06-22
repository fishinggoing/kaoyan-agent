import type {
  ApiResponse, PaginatedData,
  SchoolOption, School, Major,
  SchoolMajor,
  DecisionResult, AnalyzeResult,
  ScoreCard,
  NeedsChatResponse, PreferenceWeights,
  UserProfile, FilterOptions,
} from '../types'

const BASE = import.meta.env.VITE_API_BASE || `${window.location.origin}/api`
const REQUEST_TIMEOUT_MS = 120_000

function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  // Fallback for older browsers / non-HTTPS
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

function getClientId(): string {
  const key = '_gsc_cid'
  let cid = localStorage.getItem(key)
  if (!cid || cid.length < 8) {
    cid = generateUUID()
    localStorage.setItem(key, cid)
  }
  return cid
}

let _csrfToken: string | null = null
let _csrfPromise: Promise<string> | null = null

async function getCsrfToken(): Promise<string> {
  if (_csrfToken) return _csrfToken
  if (_csrfPromise) return _csrfPromise

  _csrfPromise = (async () => {
    const res = await fetch(`${BASE}/csrf-token`, {
      credentials: 'include',
    })
    if (!res.ok) throw new Error('Failed to fetch CSRF token')
    const body = await res.json()
    _csrfToken = body.data?.csrf_token || ''
    if (!_csrfToken) throw new Error('Empty CSRF token')
    return _csrfToken
  })()

  return _csrfPromise
}

async function buildHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Client-ID': getClientId(),
  }
  try {
    const token = await getCsrfToken()
    if (token) {
      headers['X-CSRF-Token'] = token
    }
  } catch {
    // Token fetch failed — request will be rejected by auth middleware
  }
  return headers
}

async function request<T>(url: string, options?: RequestInit): Promise<ApiResponse<T>> {
  try {
    const res = await fetch(`${BASE}${url}`, {
      headers: await buildHeaders(),
      credentials: 'include',
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      ...options,
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      let errorMsg = body.error || `HTTP ${res.status}`
      if (res.status === 503) {
        errorMsg = '请求过于频繁，请稍等片刻后再试'
      }
      return { success: false, data: null, error: errorMsg }
    }
    return res.json()
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'TimeoutError') {
      return { success: false, data: null, error: '请求超时，请检查网络连接后重试' }
    }
    return { success: false, data: null, error: `网络异常 (${err instanceof Error ? err.message : 'unknown'})` }
  }
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  schools: {
    filters: () =>
      request<FilterOptions>('/schools/filters'),
    options: (params?: Record<string, string | number>) => {
      const qs = params ? '?' + new URLSearchParams(
        Object.entries(params).filter(([_, v]) => v).map(([k, v]) => [k, String(v)])
      ).toString() : ''
      return request<PaginatedData<SchoolOption>>(`/schools/options${qs}`)
    },
    list: (params?: Record<string, string | number>) => {
      const qs = params ? '?' + new URLSearchParams(
        Object.entries(params).map(([k, v]) => [k, String(v)])
      ).toString() : ''
      return request<PaginatedData<School>>(`/schools/${qs}`)
    },
    search: (q: string, page = 1, size = 20) =>
      request<PaginatedData<School>>(`/schools/search?q=${encodeURIComponent(q)}&page=${page}&size=${size}`),
    vectorSearch: (q: string, topK = 10) =>
      request<import('../types').PaginatedData<School & { vector_relevance?: number }>>(`/schools/vector-search?q=${encodeURIComponent(q)}&top_k=${topK}`),
    get: (id: number) => request<School>(`/schools/${id}`),
  },

  majors: {
    list: (params?: Record<string, string | number>) => {
      const qs = params ? '?' + new URLSearchParams(
        Object.entries(params).map(([k, v]) => [k, String(v)])
      ).toString() : ''
      return request<PaginatedData<Major>>(`/majors/${qs}`)
    },
    get: (id: number) => request<Major>(`/majors/${id}`),
    bySchool: (schoolId: number, params?: Record<string, string | number>) => {
      const qs = params ? '?' + new URLSearchParams(
        Object.entries(params).map(([k, v]) => [k, String(v)])
      ).toString() : ''
      return request<PaginatedData<SchoolMajor>>(`/majors/school/${schoolId}${qs}`)
    },
  },

  scoreLines: {
    list: (params?: Record<string, string | number>) => {
      const qs = params ? '?' + new URLSearchParams(
        Object.entries(params).map(([k, v]) => [k, String(v)])
      ).toString() : ''
      return request<PaginatedData<SchoolMajor>>(`/score-lines/${qs}`)
    },
    getDetail: (schoolMajorId: number) =>
      request<SchoolMajor>(`/score-lines/${schoolMajorId}`),
    schoolSummary: (schoolId: number) =>
      request<{
        school_id: number; total_majors: number;
        total_planned_enrollment: number; total_push_free: number;
        majors_not_enrolling: number; majors_enrolling: number;
      }>(`/score-lines/school/${schoolId}/summary`),
    history: (schoolId: number, majorCode: string) =>
      request<import('../types').ScoreHistory>(`/score-lines/school/${schoolId}/major/${encodeURIComponent(majorCode)}/history`),
  },

  decisions: {
    recommend: (body: object) =>
      request<DecisionResult>('/decisions/recommend', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    fromChat: (body: object) =>
      request<DecisionResult>('/decisions/from-chat', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    analyze: (schoolId: number, majorCode: string, estimatedScore?: number) =>
      request<AnalyzeResult>('/decisions/analyze', {
        method: 'POST',
        body: JSON.stringify({
          school_id: schoolId,
          major_code: majorCode,
          estimated_score: estimatedScore,
        }),
      }),
  },

  profiles: {
    list: () =>
      request<import('../types').PaginatedData<UserProfile>>('/profiles/'),
    create: (data: object) =>
      request<UserProfile>('/profiles/', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    get: (id: number) =>
      request<UserProfile>(`/profiles/${id}`),
    update: (id: number, data: object) =>
      request<UserProfile>(`/profiles/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<null>(`/profiles/${id}`, { method: 'DELETE' }),
  },

  scoreCards: {
    list: (params?: Record<string, string | number>) => {
      const qs = params ? '?' + new URLSearchParams(
        Object.entries(params).map(([k, v]) => [k, String(v)])
      ).toString() : ''
      return request<import('../types').PaginatedData<ScoreCard>>(`/score-cards/${qs}`)
    },
    create: (data: object) =>
      request<ScoreCard>('/score-cards/', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<null>(`/score-cards/${id}`, { method: 'DELETE' }),
  },

  needsAnalysis: {
    chat: (data: object, signal?: AbortSignal) =>
      request<NeedsChatResponse>('/needs-analysis/chat', {
        method: 'POST',
        body: JSON.stringify(data),
        signal,
      }),
    finalize: (data: object, signal?: AbortSignal) =>
      request<NeedsChatResponse>('/needs-analysis/finalize', {
        method: 'POST',
        body: JSON.stringify(data),
        signal,
      }),
    getWeights: (profileId: number) =>
      request<PreferenceWeights>(`/needs-analysis/weights/${profileId}`),
    saveWeights: (profileId: number, weights: object) =>
      request<PreferenceWeights>(`/needs-analysis/weights/${profileId}`, {
        method: 'POST',
        body: JSON.stringify({ weights }),
      }),
  },

}

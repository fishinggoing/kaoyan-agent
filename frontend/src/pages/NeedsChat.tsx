import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Send, Loader2, User, Bot,
  CheckCircle2, Plus, Trash2, MessageSquare,
  Sparkles,
} from 'lucide-react'
import { api } from '../api/client'
import type { ChatMessage, UserProfile, IntentParams, RecommendationPreview, SchoolInfo } from '../types'
import RecommendationCard from '../components/RecommendationCard'
import SchoolInfoCard from '../components/SchoolInfoCard'

interface SavedConversation {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
  updatedAt: number
}

function genId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

function convKey(profileId: string): string {
  return `needs_conversations_${profileId}`
}

function loadConversations(profileId: string): SavedConversation[] {
  try {
    return JSON.parse(localStorage.getItem(convKey(profileId)) || '[]')
  } catch {
    return []
  }
}

function saveConversations(profileId: string, convs: SavedConversation[]) {
  localStorage.setItem(convKey(profileId), JSON.stringify(convs))
}

export default function NeedsChat() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [profileId, setProfileId] = useState(
    () => localStorage.getItem('study_profile_id') || ''
  )
  const [conversations, setConversations] = useState<SavedConversation[]>([])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [finalized, setFinalized] = useState(false)
  const [intents, setIntents] = useState<string[]>([])
  const [intentParams, setIntentParams] = useState<IntentParams>({})
  const [error, setError] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [previewData, setPreviewData] = useState<RecommendationPreview | null>(null)
  const [schoolCards, setSchoolCards] = useState<SchoolInfo[] | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const mountedRef = useRef(true)
  const abortRef = useRef<AbortController | null>(null)

  const messages = conversations.find(c => c.id === activeConvId)?.messages || []

  // Load profile on mount / profileId change
  useEffect(() => {
    if (profileId) {
      loadProfile()
      const convs = loadConversations(profileId)
      setConversations(convs)
      if (convs.length > 0) {
        setActiveConvId(convs[convs.length - 1].id)
      }
    }
  }, [profileId])

  // Persist conversations whenever they change (including empty)
  useEffect(() => {
    if (profileId) {
      saveConversations(profileId, conversations)
    }
  }, [profileId, conversations])

  // Cleanup on unmount — abort pending requests + mark unmounted
  useEffect(() => {
    return () => {
      mountedRef.current = false
      abortRef.current?.abort()
    }
  }, [])

  // Auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function loadProfile() {
    try {
      const res = await api.profiles.get(Number(profileId))
      if (res.success && res.data) {
        setProfile(res.data)
      }
    } catch (err) {
      console.error('Failed to load profile:', err)
      setProfile(null)
    }
  }

  function updateConversation(convId: string, updater: (c: SavedConversation) => SavedConversation) {
    setConversations(prev => prev.map(c => c.id === convId ? updater(c) : c))
  }

  const newConversation = useCallback(() => {
    setFinalized(false)
    setIntents([])
    setIntentParams({})
    setPreviewData(null)
    setSchoolCards(null)
    setError(null)
    const conv: SavedConversation = {
      id: genId(),
      title: '新对话',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }
    setConversations(prev => [...prev, conv])
    setActiveConvId(conv.id)
  }, [])

  function deleteConversation(id: string) {
    setConversations(prev => {
      const next = prev.filter(c => c.id !== id)
      if (activeConvId === id) {
        setActiveConvId(next.length > 0 ? next[next.length - 1].id : null)
        setFinalized(false)
        setIntents([])
        setIntentParams({})
        setPreviewData(null)
        setSchoolCards(null)
        setError(null)
      }
      return next
    })
  }

  async function executeChat(action: 'chat' | 'finalize', userMsg?: string) {
    if (!profileId || loading || !activeConvId) return
    setError(null)

    if (action === 'chat' && userMsg) {
      const msg: ChatMessage = { role: 'user', content: userMsg }
      setConversations(prev => prev.map(c => {
        if (c.id !== activeConvId) return c
        return {
          ...c,
          messages: [...c.messages, msg],
          title: c.messages.length === 0 ? userMsg.slice(0, 30) + (userMsg.length > 30 ? '…' : '') : c.title,
          updatedAt: Date.now(),
        }
      }))
    }

    setLoading(true)
    abortRef.current?.abort()
    abortRef.current = new AbortController()
    const signal = abortRef.current.signal

    try {
      const res = action === 'chat'
        ? await api.needsAnalysis.chat({
            profile_id: Number(profileId),
            message: userMsg!,
            history: messages,
          }, signal)
        : await api.needsAnalysis.finalize({
            profile_id: Number(profileId),
            history: messages,
          }, signal)

      if (!mountedRef.current) return

      const data = res.success ? res.data : null
      if (data) {
        const { reply, weights, intents, intent_params, recommendation_preview, school_cards } = data
        if (reply) {
          updateConversation(activeConvId!, c => ({
            ...c,
            messages: [...c.messages, { role: 'assistant', content: reply }],
            updatedAt: Date.now(),
          }))
        }
        setFinalized(action === 'finalize' || !!weights)
        if (intents?.length) setIntents(intents)
        if (intent_params) setIntentParams(intent_params)
        if (recommendation_preview) setPreviewData(recommendation_preview)
        if (school_cards?.length) setSchoolCards(school_cards)
      } else {
        setError(res.error || (action === 'chat' ? '对话请求失败' : '分析请求失败'))
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      if (!mountedRef.current) return
      setError('网络请求失败，请检查网络连接')
    }
    if (mountedRef.current) setLoading(false)
  }

  async function sendMessage() {
    if (!input.trim()) return
    const userMsg = input.trim()
    setInput('')
    await executeChat('chat', userMsg)
  }

  async function handleFinalize() {
    await executeChat('finalize')
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const showWelcome = !activeConvId || (messages.length === 0 && !loading)

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Sidebar toggle for mobile */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="lg:hidden fixed left-4 top-16 z-30 p-1.5 bg-white border border-slate-200 rounded-lg shadow-sm"
      >
        <MessageSquare className="w-4 h-4 text-slate-600" />
      </button>

      {/* Left sidebar — conversation history */}
      <aside className={`${
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      } lg:translate-x-0 w-64 shrink-0 border-r border-slate-200 bg-slate-50 flex flex-col transition-transform duration-200 z-20 fixed lg:relative h-full`}>
        <div className="p-3 border-b border-slate-200">
          <div className="flex items-center gap-2 mb-2">
            <label className="text-xs font-medium text-slate-500">画像</label>
            <select
              value={profileId}
              onChange={e => {
                setProfileId(e.target.value)
                if (e.target.value) {
                  const convs = loadConversations(e.target.value)
                  setConversations(convs)
                  setActiveConvId(convs.length > 0 ? convs[convs.length - 1].id : null)
                } else {
                  setConversations([])
                  setActiveConvId(null)
                }
                setFinalized(false)
                setIntents([])
                setIntentParams({})
                setError(null)
              }}
              className="flex-1 border border-slate-300 rounded-md px-2 py-1 text-xs focus:ring-2 focus:ring-purple-500 outline-none bg-white"
            >
              <option value="">选择...</option>
              {profile && <option value={String(profile.id)}>{profile.nickname}</option>}
            </select>
          </div>
          <button
            onClick={newConversation}
            disabled={!profileId}
            className="w-full flex items-center justify-center gap-1.5 py-1.5 text-sm font-medium text-purple-700 bg-purple-50 border border-purple-200 rounded-lg hover:bg-purple-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />新对话
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {conversations.length === 0 ? (
            <div className="p-4 text-center text-xs text-slate-400">
              {profileId ? '暂无对话记录' : '请先选择画像'}
            </div>
          ) : (
            conversations.slice().reverse().map(conv => (
              <button
                key={conv.id}
                onClick={() => { setActiveConvId(conv.id); setFinalized(false); setIntents([]); setPreviewData(null); setError(null) }}
                className={`w-full text-left px-3 py-2.5 border-b border-slate-100 hover:bg-slate-100 transition-colors group ${
                  activeConvId === conv.id ? 'bg-white border-l-2 border-l-purple-500' : ''
                }`}
              >
                <div className="flex items-start justify-between gap-1">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-slate-700 truncate">{conv.title}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      {new Date(conv.updatedAt).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                  <button
                    onClick={e => { e.stopPropagation(); deleteConversation(conv.id) }}
                    className="p-0.5 rounded opacity-0 group-hover:opacity-100 hover:bg-red-50 text-slate-400 hover:text-red-500 transition-all"
                    title="删除对话"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </button>
            ))
          )}
        </div>
      </aside>

      {/* Overlay for mobile sidebar */}
      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 bg-black/20 z-10" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Chat header */}
        <div className="px-4 py-3 border-b border-slate-200 bg-white flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-purple-500" />
          <h1 className="text-sm font-semibold text-slate-900">需求分析</h1>
          {finalized && (
            <span className="text-[10px] px-2 py-0.5 bg-emerald-50 border border-emerald-200 rounded text-emerald-700">
              已分析
            </span>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className="max-w-2xl mx-auto space-y-4">
            {showWelcome ? (
              <div className="flex items-center justify-center h-full py-20">
                <div className="text-center text-slate-500 max-w-md">
                  <Bot className="w-12 h-12 mx-auto mb-3 text-purple-300" />
                  <p className="font-medium mb-2 text-slate-700">你好！我是你的考研择校顾问</p>
                  <p className="text-sm text-slate-400 mb-4">
                    请告诉我你的情况——比如你本科在哪里读、想考什么方向、
                    想去哪个城市、你的职业规划等。我会帮你分析最适合的考研目标。
                  </p>
                  {!profileId && (
                    <p className="text-xs text-slate-400">请先在左侧选择一个考生画像</p>
                  )}
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg, i) => (
                  <div key={i} className={`flex items-start gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                    {msg.role === 'assistant' && (
                      <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center shrink-0">
                        <Bot className="w-4 h-4 text-purple-600" />
                      </div>
                    )}
                    <div className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-purple-600 text-white rounded-br-md'
                        : 'bg-slate-100 text-slate-700 rounded-bl-md'
                    }`}>
                      {msg.content}
                    </div>
                    {msg.role === 'user' && (
                      <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
                        <User className="w-4 h-4 text-blue-600" />
                      </div>
                    )}
                  </div>
                ))}
                {/* School info cards from [[SCHOOLS]] markers (primary) */}
                {schoolCards && schoolCards.length > 0 && !loading && (
                  <div className="mt-4 space-y-3">
                    <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
                      <Sparkles className="w-3.5 h-3.5 text-purple-500" />
                      已为你找到 {schoolCards.length} 所相关院校
                    </div>
                    {schoolCards.map((school, idx) => (
                      <SchoolInfoCard key={`${school.school_name}-${idx}`} school={school} />
                    ))}
                  </div>
                )}

                {/* Fallback: regex-based recommendation preview */}
                {!schoolCards && previewData && previewData.recommendations.length > 0 && !loading && (
                  <div className="mt-4 space-y-3">
                    <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
                      <Sparkles className="w-3.5 h-3.5 text-purple-500" />
                      已为你找到 {previewData.recommendations.length} 所匹配院校
                      {previewData.source_schools?.length > 0 && (
                        <span className="text-slate-400">
                          （{previewData.source_schools.join('、')}）
                        </span>
                      )}
                    </div>
                    {previewData.recommendations.map((rec, idx) => (
                      <RecommendationCard key={`${rec.school_name}-${rec.major_code}-${idx}`} rec={rec} index={idx} showPlanLink={false} />
                    ))}
                    {previewData.analysis && (
                      <div className="bg-gradient-to-r from-purple-50 to-blue-50 rounded-lg border border-purple-200 p-3 mt-2">
                        <p className="text-xs text-purple-800 leading-relaxed">{previewData.analysis}</p>
                      </div>
                    )}
                  </div>
                )}
                {loading && (
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center shrink-0">
                      <Bot className="w-4 h-4 text-purple-600" />
                    </div>
                    <div className="bg-slate-100 rounded-xl rounded-bl-md px-4 py-3">
                      <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </>
            )}
          </div>
        </div>

        {error && (
          <div className="px-4 py-2 text-xs text-red-600 bg-red-50 border-t border-red-100 text-center">{error}</div>
        )}

        {/* Input area */}
        {profileId && activeConvId && (
          <div className="px-4 py-3 border-t border-slate-200 bg-white">
            <div className="max-w-2xl mx-auto flex items-end gap-2">
              <textarea
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={loading}
                className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none resize-none"
                placeholder={messages.length === 0 ? "描述你的情况（如：我在河北读本科，想考计算机，偏好南方城市...）" : "输入你的想法..."}
                rows={2}
              />
              <div className="flex flex-col gap-1.5">
                <button
                  onClick={sendMessage}
                  disabled={loading || !input.trim()}
                  className="p-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <Send className="w-4 h-4" />
                </button>
                {messages.length >= 2 && (
                  <button
                    onClick={handleFinalize}
                    disabled={loading}
                    className="p-2 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100 disabled:opacity-50 transition-colors"
                    title="完成分析并保存偏好"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

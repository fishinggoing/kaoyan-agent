import { useState, useEffect } from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { GraduationCap, Search, TrendingUp, Target, MessageCircle, User, Menu, X } from 'lucide-react'
import HomePage from './pages/HomePage'
import SchoolSearch from './pages/SchoolSearch'
import ScoreAnalysis from './pages/ScoreAnalysis'
import ScoreLineDetail from './pages/ScoreLineDetail'
import DecisionPage from './pages/DecisionPage'
import NeedsChat from './pages/NeedsChat'
import OnboardingPage from './pages/OnboardingPage'
import ProfilePage from './pages/ProfilePage'

const navItems = [
  { to: '/', icon: GraduationCap, label: '首页' },
  { to: '/schools', icon: Search, label: '院校库' },
  { to: '/scores', icon: TrendingUp, label: '分数线' },
  { to: '/needs', icon: MessageCircle, label: '择校咨询' },
  { to: '/decisions', icon: Target, label: '择校匹配' },
  { to: '/profiles', icon: User, label: '个人资料' },
]

function App() {
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => { setMenuOpen(false) }, [location.pathname])

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 font-bold text-lg text-blue-800 no-underline shrink-0">
            <GraduationCap className="w-6 h-6" />
            <span className="hidden sm:inline">研择</span>
            <span className="hidden sm:inline text-xs font-normal text-slate-400 mt-0.5">考研择校平台</span>
            <span className="sm:hidden">研择</span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden lg:flex items-center gap-1">
            {navItems.map(({ to, icon: Icon, label }) => {
              const active = to === '/' ? location.pathname === '/' : location.pathname.startsWith(to)
              return (
                <Link
                  key={to}
                  to={to}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors no-underline
                    ${active ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'}`}
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </Link>
              )
            })}
          </nav>

          {/* Mobile hamburger */}
          <button
            className="lg:hidden p-2 rounded-md text-slate-600 hover:bg-slate-100"
            onClick={() => setMenuOpen(true)}
            aria-label="打开菜单"
          >
            <Menu className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* Mobile slide-in menu overlay */}
      {menuOpen && (
        <div className="lg:hidden fixed inset-0 z-50">
          <div className="fixed inset-0 bg-black/30" onClick={() => setMenuOpen(false)} />
          <div className="fixed right-0 top-0 bottom-0 w-64 bg-white shadow-xl z-10 flex flex-col">
            <div className="flex items-center justify-between px-4 h-14 border-b border-slate-200 shrink-0">
              <span className="font-semibold text-slate-700">导航菜单</span>
              <button
                className="p-1.5 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                onClick={() => setMenuOpen(false)}
                aria-label="关闭菜单"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <nav className="flex-1 overflow-y-auto py-2 px-2">
              {navItems.map(({ to, icon: Icon, label }) => {
                const active = to === '/' ? location.pathname === '/' : location.pathname.startsWith(to)
                return (
                  <Link
                    key={to}
                    to={to}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors no-underline
                      ${active ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-50'}`}
                  >
                    <Icon className="w-5 h-5 shrink-0" />
                    {label}
                  </Link>
                )
              })}
            </nav>
          </div>
        </div>
      )}


      <main className="flex-1">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/schools" element={<SchoolSearch />} />
          <Route path="/scores/:schoolId/:majorCode" element={<ScoreLineDetail />} />
          <Route path="/scores" element={<ScoreAnalysis />} />
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/needs" element={<NeedsChat />} />
          <Route path="/decisions" element={<DecisionPage />} />
          <Route path="/profiles" element={<ProfilePage />} />
        </Routes>
      </main>

      <footer className="border-t border-slate-200 py-6 text-center text-sm text-slate-400 px-4">
        研择 · 考研择校平台 — 数据驱动，科学择校
      </footer>
    </div>
  )
}

export default App

import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Search, TrendingUp, Target, Database, ChevronRight } from 'lucide-react'

const STATS = [
  { label: '覆盖院校', value: '611', unit: '所' },
  { label: '覆盖省份', value: '31', unit: '个' },
  { label: '招生专业', value: '50,000+', unit: '个' },
  { label: '数据更新', value: '每日', unit: '' },
]

const FEATURES = [
  {
    to: '/schools',
    icon: Search,
    title: '院校查询',
    desc: '查询院校招生信息、专业设置与招生目录',
    stats: '31 个省份 · 5 个办学层次',
    iconBg: 'bg-blue-600',
  },
  {
    to: '/scores',
    icon: TrendingUp,
    title: '分数线',
    desc: '查看历年复试线、招生人数与录取趋势',
    stats: '多年数据 · 趋势可视化',
    iconBg: 'bg-emerald-600',
  },
  {
    to: '/decisions',
    icon: Target,
    title: '择校匹配',
    desc: '根据成绩、地区与专业方向推荐目标院校',
    stats: '个性化匹配 · 多维度评估',
    iconBg: 'bg-red-600',
  },
]

const HOT_MAJORS = [
  '计算机科学与技术', '金融', '法律（非法学）', '临床医学',
  '教育学', '工商管理', '电子信息', '机械工程',
]

export default function HomePage() {
  const navigate = useNavigate()

  useEffect(() => {
    if (!localStorage.getItem('study_profile_id')) {
      navigate('/onboarding', { replace: true })
    }
  }, [navigate])

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Hero */}
      <section className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900 mb-2 tracking-tight">
          考研择校
          <span className="text-red-600">与院校查询</span>
          平台
        </h1>
        <p className="text-slate-600 max-w-2xl text-base leading-relaxed">
          收录全国 606 所招生院校与历年招生数据，支持院校查询、分数线分析与择校匹配。
        </p>
        <div className="flex items-center gap-3 mt-5">
          <Link
            to="/decisions"
            className="inline-flex items-center gap-1.5 px-5 py-2.5 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium text-sm no-underline"
          >
            开始择校
            <ChevronRight className="w-4 h-4" />
          </Link>
          <Link
            to="/schools"
            className="inline-flex items-center gap-1.5 px-5 py-2.5 bg-white text-slate-700 border border-slate-300 rounded-lg hover:border-slate-400 hover:bg-slate-50 transition-colors font-medium text-sm no-underline"
          >
            查询院校
          </Link>
        </div>
      </section>

      {/* Stats bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        {STATS.map(({ label, value, unit }) => (
          <div
            key={label}
            className="bg-white border border-slate-200 rounded-lg p-4 text-center"
          >
            <div className="text-2xl font-bold text-slate-900">
              {value}
              <span className="text-sm font-normal text-slate-500 ml-0.5">{unit}</span>
            </div>
            <div className="text-xs text-slate-500 mt-1">{label}</div>
          </div>
        ))}
      </div>

      {/* Feature cards */}
      <div className="grid md:grid-cols-3 gap-4 mb-8">
        {FEATURES.map(({ to, icon: Icon, title, desc, stats, iconBg }) => (
          <Link
            key={to}
            to={to}
            className="block bg-white border border-slate-200 rounded-lg p-5 hover:border-slate-300 hover:shadow-sm transition-all no-underline group"
          >
            <div className={`inline-flex p-2.5 rounded-lg ${iconBg} text-white mb-3`}>
              <Icon className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-900 mb-1 group-hover:text-red-600 transition-colors">
              {title}
            </h3>
            <p className="text-sm text-slate-500 leading-relaxed mb-2">{desc}</p>
            <span className="text-xs text-slate-400">{stats}</span>
          </Link>
        ))}
      </div>

      {/* Bottom row: hot majors + data source */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-5">
          <h3 className="font-semibold text-slate-900 mb-3 text-sm">热门专业方向</h3>
          <div className="flex flex-wrap gap-2">
            {HOT_MAJORS.map(m => (
              <Link
                key={m}
                to={`/schools?q=${encodeURIComponent(m)}`}
                className="px-3 py-1.5 bg-slate-100 text-slate-600 rounded-md text-sm hover:bg-red-50 hover:text-red-600 transition-colors no-underline"
              >
                {m}
              </Link>
            ))}
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-5">
          <h3 className="font-semibold text-slate-900 mb-3 text-sm flex items-center gap-2">
            <Database className="w-4 h-4 text-slate-500" />
            数据说明
          </h3>
          <ul className="space-y-2 text-sm text-slate-500">
            <li className="flex items-start gap-2">
              <span className="text-red-500 shrink-0 mt-0.5">·</span>
              中国研究生招生信息网（研招网）官方数据
            </li>
            <li className="flex items-start gap-2">
              <span className="text-red-500 shrink-0 mt-0.5">·</span>
              各院校研究生院官网招生简章与专业目录
            </li>
            <li className="flex items-start gap-2">
              <span className="text-red-500 shrink-0 mt-0.5">·</span>
              定期同步官方招生信息
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}

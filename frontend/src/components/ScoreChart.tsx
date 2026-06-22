import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Legend,
} from 'recharts'
import type { ScoreLine } from '../types'

interface ChartDataPoint {
  year: number
  total: number
  politics: number | null
  english: number | null
  business1: number | null
  business2: number | null
  reExamTotal: number | null
}

export default function ScoreChart({ data }: { data: ScoreLine[] }) {
  const chartData: ChartDataPoint[] = [...data]
    .sort((a, b) => a.year - b.year)
    .map(d => ({
      year: d.year,
      total: d.total_score,
      politics: d.politics_score,
      english: d.english_score,
      business1: d.business_score_1,
      business2: d.business_score_2,
      reExamTotal: d.re_exam_total_score ?? null,
    }))

  const hasReExam = chartData.some(d => d.reExamTotal)

  const minScore = Math.min(...chartData.map(d => {
    const scores = [d.total, d.politics, d.english, d.business1, d.business2].filter(Boolean) as number[]
    return Math.min(...scores)
  })) - 10

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="year" stroke="#94a3b8" fontSize={12} tickLine={false} />
        <YAxis domain={[minScore, 'auto']} stroke="#94a3b8" fontSize={12} tickLine={false} />
        <Tooltip
          contentStyle={{
            background: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            fontSize: '13px',
          }}
        />
        <Legend />
        <Line type="monotone" dataKey="total" stroke="#1e40af" strokeWidth={2.5} dot={{ r: 4 }} name="总分(初试)" />
        {hasReExam && (
          <Line type="monotone" dataKey="reExamTotal" stroke="#dc2626" strokeWidth={2} dot={{ r: 4 }} name="总分(复试)" strokeDasharray="8 4" />
        )}
        {chartData.some(d => d.politics) && (
          <Line type="monotone" dataKey="politics" stroke="#ef4444" strokeWidth={1.5} dot={{ r: 3 }} name="政治" strokeDasharray="5 5" />
        )}
        {chartData.some(d => d.english) && (
          <Line type="monotone" dataKey="english" stroke="#f59e0b" strokeWidth={1.5} dot={{ r: 3 }} name="英语" strokeDasharray="5 5" />
        )}
        {chartData.some(d => d.business1) && (
          <Line type="monotone" dataKey="business1" stroke="#10b981" strokeWidth={1.5} dot={{ r: 3 }} name="业务课1" strokeDasharray="5 5" />
        )}
        {chartData.some(d => d.business2) && (
          <Line type="monotone" dataKey="business2" stroke="#8b5cf6" strokeWidth={1.5} dot={{ r: 3 }} name="业务课2" strokeDasharray="5 5" />
        )}
      </LineChart>
    </ResponsiveContainer>
  )
}
